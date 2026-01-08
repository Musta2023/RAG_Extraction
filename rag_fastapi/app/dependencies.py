"""
Dependencies for FastAPI endpoints
"""
from fastapi import HTTPException, Depends, Request
from typing import Optional, List

from app.utils.rate_limiter import get_rate_limiter
from app.utils.logger import get_request_logger
from app.models.schemas import IngestRequest


async def validate_ingest_request(request: IngestRequest) -> bool:
    """
    Validate ingest request parameters.
    
    Returns:
        True if valid, raises HTTPException if invalid
    """
    # Check max pages limit
    if request.max_pages > 1000:
        raise HTTPException(
            status_code=400,
            detail="max_pages cannot exceed 1000"
        )
    
    # Check max depth limit
    if request.max_depth > 5:
        raise HTTPException(
            status_code=400,
            detail="max_depth cannot exceed 5"
        )
    
    # Check seed URLs count
    if len(request.seed_urls) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one seed URL is required"
        )
    
    # Check domain allowlist
    if len(request.domain_allowlist) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one domain must be allowed"
        )
    
    # Validate URLs are HTTP/HTTPS
    for url in request.seed_urls:
        url_str = str(url)
        if not url_str.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=400,
                detail=f"URL must use http:// or https:// scheme: {url_str}"
            )
    
    return True


async def get_request_context(request: Request):
    """Get request context for logging"""
    return {
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "path": request.url.path,
        "method": request.method,
    }
