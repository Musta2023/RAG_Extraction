import logging
from fastapi import APIRouter, HTTPException, status
from typing import List
from app.models.schemas import JobStatusResponse
from app.services.redis_job_service import redis_job_service
from app.config import settings
from datetime import datetime # Import datetime for type hinting

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/status/{job_id}", response_model=JobStatusResponse, summary="Get ingestion job status")
async def get_job_status(job_id: str):
    """
    Retrieves the current status of a specific ingestion job.
    """
    job = redis_job_service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found."
        )
    
    logger.info(f"Retrieved status for job {job_id}: {job.status}")
    return JobStatusResponse(**job.model_dump())

# ADDED: New endpoint for monitoring stuck jobs
@router.get("/health/jobs", response_model=List[JobStatusResponse], summary="List jobs potentially stuck or failed by watchdog")
async def get_stuck_jobs():
    """
    Retrieves a list of jobs that are not in a terminal state (completed, failed)
    and whose last_heartbeat is older than the configured WATCHDOG_THRESHOLD_SECONDS.
    These are candidates for being marked as failed by the watchdog.
    """
    try:
        stuck_jobs = redis_job_service.scan_stuck_jobs(settings.WATCHDOG_THRESHOLD_SECONDS)
        
        # Convert IngestionJob objects to JobStatusResponse schema
        return [JobStatusResponse(**job.model_dump()) for job in stuck_jobs]
    except Exception as e:
        logger.error(f"Error retrieving stuck jobs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving stuck jobs: {e}"
        )