import logging
from typing import List, Tuple
from app.core.embedder import Embedder
from app.models.document import DocumentChunk
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

class Retriever:
    """
    Retrieves relevant document chunks from the vector store based on a query.
    """
    def __init__(self, embedder: Embedder, vector_store: VectorStore):
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve_chunks(self, job_id: str, query: str, k: int = 5) -> List[Tuple[float, DocumentChunk]]:
        """
        Embeds the query and searches the vector store for the top-k most relevant chunks.

        Args:
            job_id: The ID of the ingestion job whose index to query.
            query: The user's question or query string.
            k: The number of top chunks to retrieve.

        Returns:
            A list of tuples, where each tuple contains (distance, DocumentChunk).
            Lower distance indicates higher relevance.
        """
        logger.info(f"Retrieving top {k} chunks for job {job_id} with query: '{query}'")
        try:
            query_embedding = self.embedder.embed_query(query)
            if not query_embedding:
                logger.error("Failed to generate embedding for the query.")
                return []

            results = self.vector_store.search(job_id, query_embedding, k)
            logger.info(f"Retrieved {len(results)} chunks for job {job_id}.")
            return results
        except Exception as e:
            logger.error(f"Error during retrieval for job {job_id}, query '{query}': {e}")
            return []