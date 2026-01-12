from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

# --- API Request/Response Schemas ---

class IngestRequest(BaseModel):
    """
    Schema for the POST /ingest request body.
    """
    seed_urls: List[HttpUrl] = Field(
        ...,
        description="A list of starting URLs for the crawler.",
        examples=[["https://www.example.com/start-page"]]
    )
    domain_allowlist: List[str] = Field(
        ...,
        description="A list of allowed domains for the crawler to restrict its scope (e.g., ['example.com']).",
        examples=[["example.com"]]
    )
    max_pages: int = Field(
        20,
        gt=0,
        description="Maximum number of pages to crawl.",
        examples=[20]
    )
    max_depth: int = Field(
        2,
        ge=0,
        description="Maximum depth of links to follow from seed URLs.",
        examples=[2]
    )
    user_notes: Optional[str] = Field(
        None,
        description="Optional notes from the user about this ingestion job.",
        examples=["Initial ingestion of the company blog."]
    )

class IngestResponse(BaseModel):
    """
    Schema for the POST /ingest response body.
    """
    job_id: str = Field(..., description="Unique identifier for the ingestion job.")
    message: str = Field(..., description="Status message for the job initiation.")

class Citation(BaseModel):
    """
    Schema for a single citation in the RAG answer.
    """
    url: HttpUrl = Field(..., description="URL of the source document.")
    title: Optional[str] = Field(None, description="Title of the source document.")
    chunk_id: Optional[str] = Field(None, description="Identifier for the chunk within the document.")
    quote: Optional[str] = Field(None, description="The exact quote from the source that supports the answer.")
    score: Optional[float] = Field(None, description="Relevance score of the citation to the question.")

class AskRequest(BaseModel):
    """
    Schema for the POST /ask request body.
    """
    job_id: str = Field(
        ...,
        description="The ID of the ingestion job to query against. "
                    "Only documents from this job will be used for answering.",
        examples=["some-unique-job-id"]
    )
    question: str = Field(
        ...,
        min_length=5,
        description="The question to ask the RAG system.",
        examples=["What are the main features of product X?"]
    )

class AskResponse(BaseModel):
    """
    Schema for the POST /ask response body.
    """
    answer: str = Field(..., description="The evidence-based answer to the question.")
    confidence: str = Field(..., description="Confidence level of the answer (e.g., 'high', 'medium', 'low').")
    citations: List[Citation] = Field(..., description="List of citations supporting the answer.")
    grounding_notes: Optional[str] = Field(
        None,
        description="Additional notes on how the answer was grounded, "
                    "e.g., whether multiple sources were used, or if the answer was uncertain."
    )

class JobStatusResponse(BaseModel):
    """
    Schema for the GET /status/{job_id} response body.
    """
    job_id: str = Field(..., description="Unique identifier for the ingestion job.")
    status: str = Field(..., description="Current status of the job (e.g., 'pending', 'in_progress', 'completed', 'failed').")
    started_at: datetime = Field(..., description="Timestamp when the job was started.")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when the job was completed, if applicable.")
    user_notes: Optional[str] = Field(None, description="Optional notes from the user about this ingestion job.")
    last_heartbeat: datetime = Field(..., description="Last timestamp when the job reported activity.")
    pages_fetched: int = Field(0, description="Number of pages successfully fetched.")
    pages_indexed: int = Field(0, description="Number of pages successfully indexed.")
    total_chunks_indexed: int = Field(0, description="Total number of text chunks indexed.")
    errors: List[str] = Field([], description="List of errors encountered during the job.")

class HealthCheckResponse(BaseModel):
    """
    Schema for the GET /health response body.
    """
    status: str = Field("ok", description="Status of the API service.")
    timestamp: datetime = Field(..., description="Current server time.")
    version: str = Field(..., description="Application version.")

# --- Internal Data Models ---
# These are internal models, not directly exposed via API schemas unless explicitly converted.