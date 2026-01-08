import os
import faiss
import numpy as np
import logging
from typing import List, Dict, Tuple, Optional
from threading import RLock
import json # ADDED: Import the json module
from threading import Lock
from app.models.document import DocumentChunk
from app.config import settings
from app.services.document_store import document_store # To get original documents

logger = logging.getLogger(__name__)

class VectorStore:
    """
    Manages the FAISS vector index for document chunks.
    This includes adding, searching, and persisting the index to disk.
    The index is associated with a specific job_id to allow multiple independent RAG instances.
    """
    _indexes: Dict[str, faiss.IndexFlatL2] = {} # {job_id: faiss_index}
    _chunk_metadata: Dict[str, Dict[str, DocumentChunk]] = {} # {job_id: {chunk_id: DocumentChunk}}
    _chunk_id_map: Dict[str, List[str]] = {} # {job_id: [chunk_id_1, chunk_id_2, ...]}
    _lock = RLock()
    _storage_path: str = settings.VECTOR_STORE_PATH

    def __init__(self):
        os.makedirs(self._storage_path, exist_ok=True)
        self._load_indexes_from_disk()

    def _get_index_file_path(self, job_id: str) -> str:
        """Helper to get the file path for an FAISS index."""
        return os.path.join(self._storage_path, f"index_{job_id}.faiss")

    def _get_metadata_file_path(self, job_id: str) -> str:
        """Helper to get the file path for chunk metadata."""
        return os.path.join(self._storage_path, f"metadata_{job_id}.json")

    def _get_id_map_file_path(self, job_id: str) -> str:
        """Helper to get the file path for the chunk ID map."""
        return os.path.join(self._storage_path, f"id_map_{job_id}.json")

    def _load_indexes_from_disk(self):
        """Loads all existing FAISS indexes and metadata from disk."""
        with self._lock:
            for filename in os.listdir(self._storage_path):
                if filename.startswith("index_") and filename.endswith(".faiss"):
                    job_id = filename[len("index_"):-len(".faiss")]
                    try:
                        index_path = self._get_index_file_path(job_id)
                        metadata_path = self._get_metadata_file_path(job_id)
                        id_map_path = self._get_id_map_file_path(job_id)

                        if os.path.exists(index_path) and os.path.exists(metadata_path) and os.path.exists(id_map_path):
                            self._indexes[job_id] = faiss.read_index(index_path)
                            with open(metadata_path, 'r', encoding='utf-8') as f:
                                loaded_metadata = {}
                                data = json.load(f)
                                for chunk_id, chunk_data in data.items():
                                    loaded_metadata[chunk_id] = DocumentChunk(**chunk_data)
                                self._chunk_metadata[job_id] = loaded_metadata
                            with open(id_map_path, 'r', encoding='utf-8') as f:
                                self._chunk_id_map[job_id] = json.load(f)
                            logger.info(f"Loaded FAISS index, metadata, and ID map for job {job_id}.")
                        else:
                            logger.warning(f"Incomplete index files found for job {job_id}. Skipping load.")
                            if os.path.exists(index_path): os.remove(index_path)
                            if os.path.exists(metadata_path): os.remove(metadata_path)
                            if os.path.exists(id_map_path): os.remove(id_map_path)

                    except Exception as e:
                        logger.error(f"Failed to load index for job {job_id}: {e}")
                        if job_id in self._indexes: del self._indexes[job_id]
                        if job_id in self._chunk_metadata: del self._chunk_metadata[job_id]
                        if job_id in self._chunk_id_map: del self._chunk_id_map[job_id]
                        if os.path.exists(index_path): os.remove(index_path)
                        if os.path.exists(metadata_path): os.remove(metadata_path)
                        if os.path.exists(id_map_path): os.remove(id_map_path)
            logger.info(f"Initialized VectorStore. Loaded {len(self._indexes)} indexes.")


    def _save_index(self, job_id: str):
        """Saves a specific FAISS index and its metadata to disk."""
        with self._lock:
            if job_id not in self._indexes:
                logger.warning(f"Attempted to save non-existent index for job {job_id}.")
                return

            index_path = self._get_index_file_path(job_id)
            metadata_path = self._get_metadata_file_path(job_id)
            id_map_path = self._get_id_map_file_path(job_id)

            try:
                logger.debug(f"Job {job_id}: BEFORE faiss.write_index to {index_path}.")
                faiss.write_index(self._indexes[job_id], index_path)
                logger.debug(f"Job {job_id}: AFTER faiss.write_index. BEFORE json.dump to {metadata_path}.")

                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json_compatible_metadata = {
                        chunk_id: chunk.model_dump(mode='json') for chunk_id, chunk in self._chunk_metadata[job_id].items()
                    }
                    json.dump(json_compatible_metadata, f, ensure_ascii=False, indent=4)
                
                with open(id_map_path, 'w', encoding='utf-8') as f:
                    json.dump(self._chunk_id_map[job_id], f, ensure_ascii=False, indent=4)

                logger.info(f"FAISS index, metadata, and ID map for job {job_id} saved successfully.")
            except Exception as e:
                logger.error(f"Failed to save index or metadata for job {job_id}: {e}", exc_info=True)
                raise

    def add_documents(self, job_id: str, chunks: List[DocumentChunk]) -> int:
        """
        Adds a list of DocumentChunks to the FAISS index for a given job_id.
        Creates a new index if one doesn't exist for the job_id.
        """
        if not chunks:
            return 0

        # All embeddings must have the same dimension
        embedding_dim = len(chunks[0].embedding)
        if not all(c.embedding and len(c.embedding) == embedding_dim for c in chunks):
            raise ValueError("All chunks must have embeddings of the same dimension.")

        with self._lock:
            if job_id not in self._indexes:
                # Create a new FAISS index
                index = faiss.IndexFlatL2(embedding_dim)
                self._indexes[job_id] = index
                self._chunk_metadata[job_id] = {}
                self._chunk_id_map[job_id] = []
                logger.info(f"Created new FAISS index for job {job_id} with dimension {embedding_dim}.")
            else:
                # Ensure the dimension matches existing index
                if self._indexes[job_id].d != embedding_dim:
                    raise ValueError(
                        f"Embedding dimension mismatch for job {job_id}. "
                        f"Existing: {self._indexes[job_id].d}, New: {embedding_dim}"
                    )

            num_added = 0
            for i in range(0, len(chunks), settings.FAISS_BATCH_SIZE):
                batch_chunks = chunks[i : i + settings.FAISS_BATCH_SIZE]
                
                # Prepare embeddings for FAISS
                embeddings_np = np.array([c.embedding for c in batch_chunks], dtype='float32')

                # Add vectors to index
                self._indexes[job_id].add(embeddings_np)

                # Store chunk metadata and ID map
                for chunk in batch_chunks:
                    self._chunk_metadata[job_id][chunk.chunk_id] = chunk
                    self._chunk_id_map[job_id].append(chunk.chunk_id)
                
                num_added += len(batch_chunks)
                logger.debug(f"Job {job_id}: Added {len(batch_chunks)} chunks in batch {i//settings.FAISS_BATCH_SIZE + 1}. Total added: {num_added}")

            logger.info(f"Attempting to save FAISS index and metadata for job {job_id}.")
            self._save_index(job_id) # RESTORED: _save_index call
            logger.info(f"Successfully saved FAISS index and metadata for job {job_id} after adding {num_added} chunks.")
            logger.info(f"Total indexed for job {job_id}: {self._indexes[job_id].ntotal}")
            return num_added

    def search(self, job_id: str, query_embedding: List[float], k: int = 5) -> List[Tuple[float, DocumentChunk]]:
        """
        Searches the FAISS index for the top-k most similar chunks.
        Returns a list of (distance, DocumentChunk) tuples.
        """
        with self._lock:
            if job_id not in self._indexes:
                logger.warning(f"Index for job {job_id} not found in memory. Attempting to reload all indexes from disk.")
                self._load_indexes_from_disk() # Force reload
                if job_id not in self._indexes: # Check again after reload
                    logger.warning(f"Index for job {job_id} still not found after reloading from disk. Cannot perform search.")
                    return []

            index = self._indexes[job_id]
            query_np = np.array([query_embedding], dtype='float32')

            # Ensure query embedding dimension matches index dimension
            if query_np.shape[1] != index.d:
                raise ValueError(
                    f"Query embedding dimension mismatch. "
                    f"Expected: {index.d}, Got: {query_np.shape[1]}"
                )

            distances, indices = index.search(query_np, k)

            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1: # FAISS returns -1 for empty slots if k > ntotal
                    continue
                
                # Use the robust ID map to get the chunk ID
                if job_id not in self._chunk_id_map or idx >= len(self._chunk_id_map[job_id]):
                    logger.warning(f"FAISS index {idx} out of bounds for ID map of job {job_id}. Data inconsistency.")
                    continue
                
                chunk_id = self._chunk_id_map[job_id][idx]
                
                # Retrieve the chunk metadata using the chunk ID
                chunk = self._chunk_metadata.get(job_id, {}).get(chunk_id)
                
                if chunk:
                    results.append((dist, chunk))
                else:
                    logger.warning(f"Could not find metadata for chunk ID {chunk_id} from job {job_id}. Data inconsistency.")

            # Sort by distance (smaller distance is better)
            results.sort(key=lambda x: x[0])
            return results
    
    def get_indexed_chunk(self, job_id: str, chunk_id: str) -> Optional[DocumentChunk]:
        """Retrieves a specific indexed chunk by its ID."""
        with self._lock:
            if job_id in self._chunk_metadata and chunk_id in self._chunk_metadata[job_id]:
                return self._chunk_metadata[job_id][chunk_id]
            return None

# Singleton instance
vector_store = VectorStore()
