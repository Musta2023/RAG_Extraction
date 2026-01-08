from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

class IngestionJob(BaseModel):
    """
    Represents an ingestion job, tracking its state and progress.
    """
    job_id: str
    status: str = "pending"  # e.g., "pending", "in_progress", "completed", "failed"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    pages_fetched: int = 0
    pages_indexed: int = 0
    total_chunks_indexed: int = 0
    errors: List[str] = []
    config: Dict[str, Any] = {}
    user_notes: Optional[str] = None
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow) # Added heartbeat