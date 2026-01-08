from typing import Optional
from fastapi import HTTPException, Request, status
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

# In-memory store for rate limiting. In a production environment with multiple
# instances, this should be replaced by a distributed store like Redis.
# Structure: { client_ip: { endpoint_path: [timestamp1, timestamp2, ...] } }
rate_limit_store = defaultdict(lambda: defaultdict(list))
rate_limit_lock = asyncio.Lock() # To protect access to rate_limit_store

async def rate_limit(
    request: Request,
    max_requests: int,
    time_period_seconds: int,
    client_ip: Optional[str] = None
):
    """
    Implements a simple in-memory rate limiting mechanism.

    Args:
        request: The FastAPI request object.
        max_requests: The maximum number of requests allowed within the time period.
        time_period_seconds: The time window in seconds.
        client_ip: Optional client IP. If not provided, it's extracted from the request.
    """
    if client_ip is None:
        client_ip = request.client.host if request.client else "unknown"

    endpoint_path = request.url.path

    async with rate_limit_lock:
        current_time = datetime.now()
        
        # Filter out requests older than the time_period
        rate_limit_store[client_ip][endpoint_path] = [
            t for t in rate_limit_store[client_ip][endpoint_path]
            if current_time - t < timedelta(seconds=time_period_seconds)
        ]

        if len(rate_limit_store[client_ip][endpoint_path]) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {time_period_seconds} seconds."
            )
        
        rate_limit_store[client_ip][endpoint_path].append(current_time)