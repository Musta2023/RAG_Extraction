import time
import logging
from contextlib import asynccontextmanager # Import for lifespan management
from fastapi import FastAPI, Request
from app.api.routers import health, ingest, status, ask
from app.config import settings
from app.services.vector_store import vector_store # Import vector_store for initialization check
from app.services.redis_job_service import redis_job_service # Updated import
from app.utils.logger import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for managing the lifespan of the FastAPI application.
    Handles startup and shutdown events.
    """
    logger.info("Application startup...")
    # Initialize services that need it, e.g., load models or data
    vector_store # Accessing the singleton instance to ensure it's initialized
    redis_job_service # Accessing the singleton instance to ensure it's initialized
    yield # Application runs
    logger.info("Application shutdown...")
    # Clean up resources if necessary

# Create FastAPI app instance
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A FastAPI application for web-based Retrieval-Augmented Generation.",
    lifespan=lifespan # Assign the lifespan manager
)

# Add a middleware to log requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log incoming requests and their processing time.
    """
    start_time = time.time()
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Request finished: {request.method} {request.url.path} with status {response.status_code} in {process_time:.4f}s")
    return response

# Include API routers
app.include_router(health.router, prefix=settings.API_PREFIX, tags=["Health"])
app.include_router(ingest.router, prefix=settings.API_PREFIX, tags=["Ingestion"])
app.include_router(status.router, prefix=settings.API_PREFIX, tags=["Status"])
app.include_router(ask.router, prefix=settings.API_PREFIX, tags=["Q&A"])

@app.get("/", tags=["Root"])
async def read_root():
    """
    Root endpoint providing a welcome message.
    """
    return {"message": f"Welcome to {settings.APP_NAME}!"}