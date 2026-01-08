# API routers package
"""
API routers initialization
"""
from .health import router as health_router
from .ingest import router as ingest_router
from .ask import router as ask_router
from .status import router as status_router

__all__ = ["health_router", "ingest_router", "ask_router", "status_router"]
