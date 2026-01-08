from celery import Celery
from app.config import settings

# Initialize Celery
celery = Celery(
    'rag_fastapi',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.background.tasks']
)

# Optional: Configure Celery
celery.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    result_expires=3600,  # Results expire after 1 hour
    task_soft_time_limit=3600,   # Default soft time limit for all tasks (1 hour)
    task_time_limit=3700         # Default hard time limit (slightly longer)
)
