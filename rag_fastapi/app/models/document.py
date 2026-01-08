from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

class Document(BaseModel):
    """
    Represents a single web document that has been crawled and processed.
    """
    url: HttpUrl
    title: Optional[str] = None
    text_content: str  # The main extracted text content of the document
    html_content: Optional[str] = None # Original HTML content, stored for reference if needed
    fetch_timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {} # Additional metadata, e.g., author, publication date, etc.

class DocumentChunk(BaseModel):
    """
    Represents a chunk of text derived from a Document, suitable for embedding.
    """
    chunk_id: str # Unique identifier for this chunk (e.g., hash of content + URL + index)
    document_url: HttpUrl # Reference to the source document
    document_title: Optional[str] = None # Reference to the source document title
    text_content: str # The actual text content of the chunk
    start_index: int # Starting character index of the chunk in the original document_text
    end_index: int # Ending character index of the chunk in the original document_text
    embedding: Optional[List[float]] = None # The vector embedding of the text_content
    metadata: Dict[str, Any] = {} # Any additional metadata specific to this chunk