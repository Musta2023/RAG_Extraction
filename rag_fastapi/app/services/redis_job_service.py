import redis
import os
from typing import Dict, Optional, List, Any
from threading import Lock
from datetime import datetime, timedelta # Import timedelta
from app.models.job import IngestionJob
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class RedisJobService:
    """
    Manages the state and persistence of ingestion jobs using Redis.
    Each IngestionJob is stored as a JSON string in Redis.
    """
    _redis_client: Optional[redis.Redis] = None
    _lock = Lock()
    _initialized: bool = False

    def __init__(self):
        # Initialize Redis client only once for the singleton
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    try:
                        # Use the broker URL from Celery settings for consistency
                        redis_url = os.getenv("REDIS_URL")
                        if not redis_url:
                            if os.getenv("IS_DOCKERIZED", "false").lower() == "true":
                                redis_url = "redis://redis:6379/0"
                            else:
                                redis_url = "redis://localhost:6379/0"
                        self._redis_client = redis.from_url(redis_url, decode_responses=True)
                        self._redis_client.ping()
                        logger.info("Connected to Redis successfully for JobService.")
                        self._initialized = True
                    except redis.exceptions.ConnectionError as e:
                        logger.error(f"Could not connect to Redis for JobService: {e}")
                        self._redis_client = None
                        raise ConnectionError("Failed to connect to Redis") from e
                    except Exception as e:
                        logger.error(f"An unexpected error occurred during Redis initialization: {e}")
                        self._redis_client = None
                        raise

    def _get_job_key(self, job_id: str) -> str:
        return f"ingestion_job:{job_id}"

    def create_job(self, job: IngestionJob):
        """Adds a new job to Redis."""
        if not self._redis_client:
            raise ConnectionError("Redis client is not initialized.")
        
        job_key = self._get_job_key(job.job_id)
        job.last_heartbeat = datetime.utcnow() # Set heartbeat on creation
        job_json = job.model_dump_json()
        
        try:
            self._redis_client.set(job_key, job_json)
            logger.info(f"Job {job.job_id} created and stored in Redis.")
        except Exception as e:
            logger.error(f"Failed to create job {job.job_id} in Redis: {e}")
            raise

    def get_job(self, job_id: str) -> Optional[IngestionJob]:
        """Retrieves a job by its ID from Redis."""
        if not self._redis_client:
            raise ConnectionError("Redis client is not initialized.")
        
        job_key = self._get_job_key(job_id)
        try:
            job_json = self._redis_client.get(job_key)
            if job_json:
                return IngestionJob.model_validate_json(job_json)
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve job {job_id} from Redis: {e}")
            raise

    def update_job(self, job: IngestionJob):
        """Updates an existing job in Redis."""
        if not self._redis_client:
            raise ConnectionError("Redis client is not initialized.")
        
        job_key = self._get_job_key(job.job_id)
        job.last_heartbeat = datetime.utcnow() # Update heartbeat on every update
        job_json = job.model_dump_json()
        
        try:
            self._redis_client.set(job_key, job_json)
            logger.debug(f"Job {job.job_id} updated in Redis to status: {job.status}")
        except Exception as e:
            logger.error(f"Failed to update job {job.job_id} in Redis: {e}")
            raise

    def get_all_jobs(self) -> Dict[str, IngestionJob]:
        """Returns all managed jobs from Redis."""
        if not self._redis_client:
            raise ConnectionError("Redis client is not initialized.")
        
        jobs_dict: Dict[str, IngestionJob] = {}
        try:
            for key in self._redis_client.scan_iter(self._get_job_key("*")):
                job_id = key.split(":")[-1]
                job = self.get_job(job_id)
                if job:
                    jobs_dict[job_id] = job
            return jobs_dict
        except Exception as e:
            logger.error(f"Failed to retrieve all jobs from Redis: {e}")
            raise

    def scan_stuck_jobs(self, threshold_seconds: int) -> List[IngestionJob]:
        """
        Scans for jobs that are not in a terminal state ('completed', 'failed')
        and whose last_heartbeat is older than the given threshold.
        """
        if not self._redis_client:
            raise ConnectionError("Redis client is not initialized.")
        
        stuck_jobs: List[IngestionJob] = []
        now = datetime.utcnow()
        inactivity_threshold = timedelta(seconds=threshold_seconds)

        logger.debug(f"Scanning for stuck jobs with inactivity threshold: {inactivity_threshold}")

        try:
            for key in self._redis_client.scan_iter(self._get_job_key("*")):
                job_id = key.split(":")[-1]
                job = self.get_job(job_id)
                
                if job and job.status not in ["completed", "failed"]:
                    if job.last_heartbeat and (now - job.last_heartbeat) > inactivity_threshold:
                        stuck_jobs.append(job)
                        logger.warning(
                            f"Job {job.job_id} detected as stuck. "
                            f"Status: {job.status}, Last Heartbeat: {job.last_heartbeat} (older than {threshold_seconds}s)"
                        )
            return stuck_jobs
        except Exception as e:
            logger.error(f"Error scanning for stuck jobs in Redis: {e}", exc_info=True)
            raise

    def delete_all_jobs(self):
        """Deletes all jobs from Redis. Primarily for testing."""
        if not self._redis_client:
            raise ConnectionError("Redis client is not initialized.")
        
        try:
            keys = list(self._redis_client.scan_iter(self._get_job_key("*")))
            if keys:
                self._redis_client.delete(*keys)
            logger.info(f"Deleted {len(keys)} jobs from Redis.")
        except Exception as e:
            logger.error(f"Failed to delete jobs from Redis: {e}")
            raise

# Singleton instance for RedisJobService
redis_job_service = RedisJobService()