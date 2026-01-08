import logging
from fastapi import APIRouter, HTTPException, status
from app.models.schemas import AskRequest, AskResponse
from app.services.redis_job_service import redis_job_service # Updated import
from app.services.vector_store import VectorStore
from app.core.embedder import Embedder
from app.core.retriever import Retriever
from app.core.generator import Generator
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize core RAG components
embedder = Embedder()
vector_store = VectorStore()
retriever = Retriever(embedder=embedder, vector_store=vector_store)
generator = Generator()

@router.post("/ask", response_model=AskResponse, summary="Ask a question against an indexed job")
async def ask_question(request: AskRequest):
    """
    Accepts a question and a job ID, retrieves relevant information from the
    indexed content of that job, and generates an evidence-based answer.
    """
    job = redis_job_service.get_job(request.job_id) # Updated service call

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{request.job_id}' not found."
        )

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job '{request.job_id}' is not completed yet. Current status: {job.status}. "
                   "Please wait for the ingestion to finish before asking questions."
        )
    
    logger.info(f"Received ask request for job {request.job_id}, question: '{request.question}'")

    try:
        # Step 1: Retrieve relevant chunks
        retrieved_chunks = retriever.retrieve_chunks(request.job_id, request.question, k=settings.RETRIEVER_TOP_K)
        
        # Step 2: Generate answer
        answer_data = await generator.generate_answer(request.question, retrieved_chunks, request.job_id)
        
        return AskResponse(
            answer=answer_data["answer"],
            confidence=answer_data["confidence"],
            citations=answer_data["citations"],
            grounding_notes=answer_data["grounding_notes"]
        )

    except Exception as e:
        logger.error(f"Error processing ask request for job {request.job_id}, question '{request.question}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing your question: {e}"
        )