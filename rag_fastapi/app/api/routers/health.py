from datetime import datetime
from fastapi import APIRouter
from app.models.schemas import HealthCheckResponse
from app.config import settings

router = APIRouter()

@router.get("/health", response_model=HealthCheckResponse, summary="Perform a health check")
async def health_check():
    """
    Performs a health check on the API service.
    Returns:
        HealthCheckResponse: The current status of the service.
    """
    return HealthCheckResponse(
        status="ok",
        timestamp=datetime.utcnow(),
        version=settings.APP_VERSION
    )