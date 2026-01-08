import uuid
import logging
from datetime import datetime, timedelta # Import timedelta for watchdog
import asyncio
import redis
from redlock import Redlock
from urllib.parse import urlparse
from celery.exceptions import SoftTimeLimitExceeded # ADDED: Import for time limit handling

from app.background.celery_worker import celery
from app.config import settings
from app.models.job import IngestionJob
from app.models.schemas import IngestRequest
from app.services.redis_job_service import redis_job_service
from app.core.crawler import WebCrawler
from app.core.processor import DocumentProcessor
from app.core.embedder import Embedder
from app.core.generator import Generator
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)

# Parse Redis URL from settings
redis_url = urlparse(settings.CELERY_BROKER_URL)
redis_host = redis_url.hostname
redis_port = redis_url.port
redis_db = int(redis_url.path[1:]) if redis_url.path else 0
redis_password = redis_url.password

# Initialize Redis client for Redlock
redis_client = redis.StrictRedis(
    host=redis_host,
    port=redis_port,
    db=redis_db,
    password=redis_password
)
dlm = Redlock([redis_client])

# Initialize singletons
crawler = WebCrawler(
    user_agent=settings.CRAWLER_USER_AGENT,
    request_timeout=settings.CRAWLER_REQUEST_TIMEOUT,
    max_retries=settings.CRAWLER_MAX_RETRIES
)
processor = DocumentProcessor()


async def _run_ingestion_async(job_id: str, ingest_request: IngestRequest):
    """
    Internal asynchronous function to handle the core ingestion logic.
    """
    # Initialize factories
    embedder = Embedder()
    generator = Generator()

    job = redis_job_service.get_job(job_id)
    if not job:
        logger.error(f"Ingestion job {job_id} not found in Redis.")
        return

    # CHANGED: Initial status set to 'pending' (this is just before pipeline starts)
    job.status = "pending"
    # job.last_heartbeat will be set by redis_job_service.update_job
    redis_job_service.update_job(job)
    logger.info(f"Starting pipeline for Job {job_id}")

    try:
        # CHANGED: Update status to 'crawling' with heartbeat
        job.status = "crawling"
        redis_job_service.update_job(job)
        logger.info(f"Job {job_id} status updated to 'crawling'.")

        # ADDED: Debugging Redlock acquisition
        logger.debug(f"Job {job_id}: Checking Redis client connection for Redlock: {redis_client.ping()}")
        
        crawl_urls = []
        for url_to_crawl in ingest_request.seed_urls:
            lock_key = f"crawl_lock:{str(url_to_crawl)}"
            logger.debug(f"Job {job_id}: Attempting to acquire lock for {url_to_crawl} with key {lock_key}, TTL {300000}ms.")
            lock = dlm.lock(lock_key, ttl=300000)  # Lock for 5 minutes
            logger.debug(f"Job {job_id}: Lock acquisition result for {url_to_crawl}: {lock}")
            
            if lock:
                logger.info(f"Acquired lock for {url_to_crawl}. Proceeding to crawl.")
                crawl_urls.append(str(url_to_crawl))
            else:
                logger.warning(f"Skipping {url_to_crawl}. Another worker is already crawling or recently crawled this URL.")

        if not crawl_urls:
            raise ValueError("All specified URLs were skipped due to existing locks or no URLs to crawl.")

        crawled_documents = await crawler.crawl(
            seed_urls=crawl_urls,
            domain_allowlist=ingest_request.domain_allowlist,
            max_pages=ingest_request.max_pages,
            max_depth=ingest_request.max_depth,
            job_id=job_id
        )

        if not crawled_documents:
            raise ValueError("No documents were fetched.")

        job.pages_fetched = len(crawled_documents)
        redis_job_service.update_job(job) # Update after crawling

        # CHANGED: Update status to 'processing' with heartbeat
        job.status = "processing"
        redis_job_service.update_job(job)
        logger.info(f"Job {job_id} status updated to 'processing'.")

        all_chunks = []
        for doc in crawled_documents:
            processed_chunks = processor.process_document(doc)
            all_chunks.extend(processed_chunks)

        # CHANGED: Update status to 'embedding' with heartbeat
        job.status = "embedding"
        redis_job_service.update_job(job)
        logger.info(f"Job {job_id} status updated to 'embedding'.")

        chunk_texts = [chunk.text_content for chunk in all_chunks]
        embeddings = embedder.embed_documents(chunk_texts)

        if not embeddings:
            raise ValueError("Embedding generation failed.")

        for i, chunk in enumerate(all_chunks):
            chunk.embedding = embeddings[i]

        # CHANGED: Update status to 'indexing' with heartbeat
        job.status = "indexing"
        redis_job_service.update_job(job)
        logger.info(f"Job {job_id} status updated to 'indexing' before FAISS operation.")

        indexed_count = vector_store.add_documents(job_id, all_chunks)
        logger.debug(f"Job {job_id}: vector_store.add_documents returned {indexed_count} indexed chunks.")

        if indexed_count == 0 and all_chunks:
            job.status = "failed"
            job.errors.append("No chunks were indexed despite documents being available for processing.")
            logger.error(f"Job {job_id} FAILED: No chunks indexed.")
        else:
            job.pages_indexed = job.pages_fetched
            job.total_chunks_indexed = indexed_count
            job.status = "completed"
            logger.info(f"Job {job_id} SUCCESS: {indexed_count} chunks indexed.")

    # CHANGED: Handle SoftTimeLimitExceeded
    except SoftTimeLimitExceeded:
        logger.error(f"Job {job_id} FAILED: Soft time limit exceeded. Task will be terminated soon.", exc_info=True)
        job.status = "failed"
        job.errors.append("Ingestion task exceeded soft time limit.")
        job.pages_indexed = 0
        job.total_chunks_indexed = 0
    except Exception as e:
        logger.error(f"Job {job_id} FAILED due to exception: {str(e)}", exc_info=True)
        job.status = "failed"
        job.errors.append(f"Ingestion failed: {str(e)}")
        job.pages_indexed = 0
        job.total_chunks_indexed = 0

    finally:
        job.completed_at = datetime.utcnow()
        try:
            redis_job_service.update_job(job)
            logger.debug(f"Job {job_id}: Final status '{job.status}' updated in Redis.")
        except Exception as redis_e:
            logger.critical(f"Job {job_id}: CRITICAL ERROR updating final job status in Redis: {redis_e}", exc_info=True)

        if job.status == "failed": # CHANGED: Check job.status to determine if we should re-raise
            raise ValueError(f"Job {job_id} failed, check logs for details.")


# CHANGED: Apply Celery time limits
@celery.task(
    bind=True,
    name='ingestion_task',
    soft_time_limit=settings.CELERY_SOFT_TIME_LIMIT,
    time_limit=settings.CELERY_HARD_TIME_LIMIT
)
def ingestion_task(self, job_id: str, ingest_request_dict: dict):
    """
    Celery task wrapper for the ingestion pipeline.
    """
    ingest_request = IngestRequest(**ingest_request_dict)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_ingestion_async(job_id, ingest_request))
    finally:
        loop.close()


# ADDED: Watchdog task
@celery.task(bind=True, name='watchdog_task')
def watchdog_task(self):
    """
    Celery task to periodically scan for and mark stuck ingestion jobs as failed.
    """
    logger.info("Watchdog task started: Scanning for stuck jobs.")
    try:
        stuck_jobs = redis_job_service.scan_stuck_jobs(settings.WATCHDOG_THRESHOLD_SECONDS)
        
        if not stuck_jobs:
            logger.info("Watchdog found no stuck jobs.")
            return

        for job in stuck_jobs:
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.errors.append(f"Marked failed by watchdog due to inactivity exceeding {settings.WATCHDOG_THRESHOLD_SECONDS} seconds.")
            try:
                redis_job_service.update_job(job)
                logger.warning(
                    f"Watchdog marked job {job.job_id} as 'failed' due to inactivity. "
                    f"Last heartbeat: {job.last_heartbeat}"
                )
            except Exception as e:
                logger.critical(
                    f"Watchdog CRITICAL ERROR: Could not update job {job.job_id} status to 'failed' in Redis: {e}",
                    exc_info=True
                )
    except Exception as e:
        logger.error(f"Watchdog task encountered an unhandled exception: {e}", exc_info=True)


