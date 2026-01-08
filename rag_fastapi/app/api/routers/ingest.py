import uuid
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from app.models.schemas import IngestRequest, IngestResponse
from app.models.job import IngestionJob
from app.services.redis_job_service import redis_job_service # Updated import
from app.background.tasks import ingestion_task # Celery task
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED, summary="Start web content ingestion")
async def ingest_content(request: IngestRequest):
    """
    Initiates a background task to crawl web content from specified URLs,
    clean, chunk, embed, and index it into the vector store.
    """
    job_id = str(uuid.uuid4())
    
    # Store initial job configuration
    # Convert HttpUrl objects in seed_urls to strings for JSON serialization by Celery
    job_config = request.model_dump()
    job_config["seed_urls"] = [str(url) for url in request.seed_urls]

    # Create and store the initial job status using RedisJobService
    job = IngestionJob(
        job_id=job_id,
        status="pending",
        config=job_config,
        user_notes=request.user_notes
    )
    redis_job_service.create_job(job) # Updated service call
    
    # Enqueue the ingestion task with Celery
    ingestion_task.delay(job_id, job_config)
    
    logger.info(f"Ingestion job {job_id} initiated for URLs: {request.seed_urls[:5]}...")
    
    return IngestResponse(
        job_id=job_id,
        message="Ingestion job started. Check status using GET /status/{job_id}"
    )