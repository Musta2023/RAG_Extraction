import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock # Added AsyncMock
from datetime import datetime, timedelta
from app.main import app
from app.services import redis_job_service as job_service
from app.models.job import IngestionJob
from app.models.schemas import AskRequest, IngestRequest, Citation
from app.config import settings
import json # Added import

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_job_service():
    """Clear jobs before each test by deleting them from Redis."""
    # Ensure RedisJobService is initialized and has a client
    if job_service._redis_client is None:
        job_service.__init__() 

    # Delete all keys matching the job prefix
    job_keys = list(job_service._redis_client.scan_iter("ingestion_job:*"))
    if job_keys:
        job_service._redis_client.delete(*job_keys)
    yield
    # Clean up after test if necessary, though autouse usually handles setup.
    # We re-clear to ensure a clean state for subsequent test runs if not all tests use the autouse fixture.
    job_keys_after = list(job_service._redis_client.scan_iter("ingestion_job:*"))
    if job_keys_after:
        job_service._redis_client.delete(*job_keys_after)

@pytest.fixture
def mock_ingestion_task():
    """Mock the Celery ingestion task."""
    with patch("app.api.routers.ingest.ingestion_task") as mock_task:
        mock_task.delay.return_value = MagicMock(id="mock_task_id")
        yield mock_task

@pytest.fixture
def mock_retriever_generator():
    """Mock the Retriever and Generator components for /ask endpoint."""
    with patch("app.api.routers.ask.retriever") as mock_ret, \
         patch("app.api.routers.ask.generator") as mock_gen:
        yield mock_ret, mock_gen

def test_health_check():
    """Test the /health endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "timestamp" in response.json()
    assert response.json()["version"] == settings.APP_VERSION

def test_ingest_content_success(mock_ingestion_task):
    """Test POST /ingest endpoint successfully starts a job."""
    test_request_payload = {
        "seed_urls": ["http://example.com"],
        "domain_allowlist": ["example.com"],
        "max_pages": 1,
        "max_depth": 0,
        "user_notes": "Test ingestion"
    }
    response = client.post("/api/ingest", json=test_request_payload)
    
    assert response.status_code == 202
    response_json = response.json()
    assert "job_id" in response_json
    assert "message" in response_json
    assert "Ingestion job started" in response_json["message"]

    # Verify job was created in job_service
    job = job_service.get_job(response_json["job_id"])
    assert job is not None
    assert job.status == "pending"
    assert job.user_notes == "Test ingestion"
    assert job.config["max_pages"] == 1
    
    # Verify Celery task was called
    expected_args = json.loads(IngestRequest(**test_request_payload).model_dump_json())
    mock_ingestion_task.delay.assert_called_once_with(
        response_json["job_id"],
        expected_args
    )

def test_get_job_status_pending():
    """Test GET /status/{job_id} for a pending job."""
    job_id = "test_pending_job"
    test_job = IngestionJob(
        job_id=job_id,
        status="pending",
        started_at=datetime.utcnow() - timedelta(minutes=5),
        config={"seed_urls": ["http://example.com"]},
        user_notes="Pending test"
    )
    job_service.create_job(test_job)

    response = client.get(f"/api/status/{job_id}")
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["job_id"] == job_id
    assert response_json["status"] == "pending"
    assert response_json["pages_fetched"] == 0
    assert response_json["errors"] == []
    assert response_json["user_notes"] == "Pending test"

def test_get_job_status_completed():
    """Test GET /status/{job_id} for a completed job."""
    job_id = "test_completed_job"
    started = (datetime.utcnow() - timedelta(minutes=10)).replace(microsecond=0)
    completed = (datetime.utcnow() - timedelta(minutes=1)).replace(microsecond=0)
    test_job = IngestionJob(
        job_id=job_id,
        status="completed",
        started_at=started,
        completed_at=completed,
        pages_fetched=10,
        pages_indexed=8,
        total_chunks_indexed=50,
        config={"seed_urls": ["http://example.com"]},
        user_notes="Completed test"
    )
    job_service.create_job(test_job)

    response = client.get(f"/api/status/{job_id}")
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["job_id"] == job_id
    assert response_json["status"] == "completed"
    assert response_json["pages_fetched"] == 10
    assert response_json["pages_indexed"] == 8
    assert response_json["total_chunks_indexed"] == 50
    assert response_json["errors"] == []
    response_started_at = datetime.fromisoformat(response_json["started_at"]).replace(microsecond=0)
    response_completed_at = datetime.fromisoformat(response_json["completed_at"]).replace(microsecond=0) if response_json["completed_at"] else None
    assert response_started_at == started
    assert response_completed_at == completed


def test_get_job_status_not_found():
    """Test GET /status/{job_id} for a non-existent job."""
    response = client.get("/api/status/non_existent_job")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_ask_question_job_not_found():
    """Test POST /ask when job_id does not exist."""
    ask_payload = {"job_id": "non_existent_job", "question": "What is foo?"}
    response = client.post("/api/ask", json=ask_payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_ask_question_job_not_completed():
    """Test POST /ask when job_id exists but is not completed."""
    job_id = "test_in_progress_job"
    test_job = IngestionJob(job_id=job_id, status="in_progress", started_at=datetime.utcnow())
    job_service.create_job(test_job)

    ask_payload = {"job_id": job_id, "question": "What is foo?"}
    response = client.post("/api/ask", json=ask_payload)
    assert response.status_code == 409
    assert "not completed yet" in response.json()["detail"].lower()

@patch("app.api.routers.ask.retriever")
@patch("app.api.routers.ask.generator.generate_answer") # Patch the method directly
def test_ask_question_success(mock_generate_answer, mock_retriever):
    """Test POST /ask successfully returns an answer."""
    job_id = "test_completed_job_for_ask"
    test_job = IngestionJob(job_id=job_id, status="completed", started_at=datetime.utcnow(), completed_at=datetime.utcnow())
    job_service.create_job(test_job)

    mock_retriever.retrieve_chunks.return_value = [
                    (0.1, MagicMock(spec=Citation, document_url="http://src1.com", text_content="Source 1 content")),        (0.2, MagicMock(spec=Citation, document_url="http://src2.com", text_content="Source 2 content"))
    ]
    mock_generate_answer.return_value = {
        "answer": "The answer is from source 1 [Source 1].",
        "confidence": "high",
        "citations": ["http://src1.com"], # Updated to List[str]
        "grounding_notes": "Generated from 1 source."
    }

    ask_payload = {"job_id": job_id, "question": "What is the answer?"}
    response = client.post("/api/ask", json=ask_payload)
    
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["answer"] == "The answer is from source 1 [Source 1]."
    assert response_json["confidence"] == "high"
    assert len(response_json["citations"]) == 1
    assert response_json["citations"][0] == "http://src1.com" # Changed from .url to direct string
    assert response_json["grounding_notes"] == "Generated from 1 source."

    mock_retriever.retrieve_chunks.assert_called_once_with(job_id, "What is the answer?", k=settings.RETRIEVER_TOP_K)
    mock_generate_answer.assert_called_once()