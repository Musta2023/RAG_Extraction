import uuid
import logging
from typing import List
from bs4 import BeautifulSoup
from app.models.document import Document, DocumentChunk
from app.utils.text_utils import clean_html, chunk_text # Assuming you have text_utils

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """
    Processes raw HTML documents: cleans them, extracts main text,
    and chunks the text into smaller, embeddable passages.
    """
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def process_document(self, document: Document) -> List[DocumentChunk]:
        """
        Cleans the HTML content of a document and
        chunks its text into DocumentChunk objects.
        """
        if not document.html_content:
            logger.warning(f"Document {document.url} has no HTML content to process.")
            return []

        # 1. Clean HTML and extract main text
        cleaned_text = clean_html(document.html_content)
        document.text_content = cleaned_text # Update the document with cleaned text

        if not cleaned_text:
            logger.warning(f"No meaningful text extracted from {document.url}.")
            return []

        # 2. Chunk the cleaned text
        text_chunks = chunk_text(cleaned_text, self.chunk_size, self.chunk_overlap)
        
        document_chunks: List[DocumentChunk] = []
        current_idx = 0
        for i, text_chunk in enumerate(text_chunks):
            # Find the actual start and end index in the original cleaned_text
            # This is a simplification; a more robust approach would track this
            # during the chunk_text function itself.
            start_index = cleaned_text.find(text_chunk, current_idx)
            if start_index == -1:
                # If chunk not found from current_idx, search from beginning
                start_index = cleaned_text.find(text_chunk)
                if start_index == -1:
                    logger.warning(f"Could not find text_chunk in cleaned_text for {document.url}. Skipping chunk.")
                    continue
            end_index = start_index + len(text_chunk)
            current_idx = end_index # Update current_idx for next search

            chunk_id = f"{document.url.host}-{uuid.uuid4().hex[:8]}-{i}"

            chunk = DocumentChunk(
                chunk_id=chunk_id,
                document_url=document.url,
                document_title=document.title,
                text_content=text_chunk,
                start_index=start_index,
                end_index=end_index,
                metadata={
                    "source": str(document.url),
                    "fetch_timestamp": document.fetch_timestamp.isoformat(),
                    **document.metadata
                }
            )
            document_chunks.append(chunk)

        logger.info(f"Processed {document.url}: generated {len(document_chunks)} chunks.")
        return document_chunks