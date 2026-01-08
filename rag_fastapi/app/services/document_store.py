import json
import os
from typing import Dict, List, Optional
from threading import Lock
from app.models.document import Document
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class DocumentStore:
    """
    Manages the storage and retrieval of raw Document objects.
    In a production environment, this would likely be a proper database (e.g., PostgreSQL, MongoDB)
    or a document storage service. For this project, we use a simple file-based approach
    where each document is stored as a JSON file.
    """
    _documents: Dict[str, Document] = {} # In-memory cache
    _lock = Lock()
    _storage_path: str = settings.DOCUMENT_STORE_PATH

    def __init__(self):
        os.makedirs(self._storage_path, exist_ok=True)
        # In a real app, you might load all docs on startup, but for potentially many files,
        # it's better to load on demand or use a proper database.
        # We'll just ensure the directory exists and track current files.
        self._initialize_from_disk()

    def _get_document_file_path(self, doc_id: str) -> str:
        """Helper to get the file path for a document."""
        return os.path.join(self._storage_path, f"doc_{doc_id}.json")

    def _initialize_from_disk(self):
        """
        Scan the storage path to find existing document IDs.
        Does not load full documents into memory immediately.
        """
        with self._lock:
            self._documents = {} # Clear cache
            for filename in os.listdir(self._storage_path):
                if filename.startswith("doc_") and filename.endswith(".json"):
                    doc_id = filename[len("doc_"):-len(".json")]
                    # Store a placeholder or minimal info, full document loaded on demand
                    # For simplicity, we'll keep a reference by ID, and load full object when get_document is called
                    self._documents[doc_id] = None # Placeholder, signals existence without loading
            logger.info(f"Initialized document store. Found {len(self._documents)} existing document IDs.")

    def add_document(self, doc_id: str, document: Document):
        """Adds a document to the store and persists it to disk."""
        with self._lock:
            if doc_id in self._documents and self._documents[doc_id] is not None:
                logger.warning(f"Document with ID {doc_id} already exists in store. Overwriting.")
            
            file_path = self._get_document_file_path(doc_id)
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    # Use model_dump to handle datetime and HttpUrl correctly for JSON serialization
                    json.dump(document.model_dump(mode='json'), f, ensure_ascii=False, indent=4)
                self._documents[doc_id] = document # Add to in-memory cache
                logger.debug(f"Document {doc_id} saved to {file_path}")
            except Exception as e:
                logger.error(f"Failed to save document {doc_id} to {file_path}: {e}")
                raise

    def get_document(self, doc_id: str) -> Optional[Document]:
        """Retrieves a document by its ID, loading from disk if not in cache."""
        with self._lock:
            if doc_id not in self._documents:
                return None
            
            # If not in cache or is a placeholder, load from disk
            if self._documents[doc_id] is None:
                file_path = self._get_document_file_path(doc_id)
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            # Re-parse to Pydantic model to ensure correct types (e.g., datetime)
                            self._documents[doc_id] = Document(**data)
                            logger.debug(f"Document {doc_id} loaded from {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to load document {doc_id} from {file_path}: {e}")
                        return None
                else:
                    logger.warning(f"Document {doc_id} expected at {file_path} but not found on disk.")
                    del self._documents[doc_id] # Clean up
                    return None
            
            return self._documents[doc_id]

    def get_documents_by_ids(self, doc_ids: List[str]) -> Dict[str, Document]:
        """Retrieves multiple documents by their IDs."""
        results = {}
        for doc_id in doc_ids:
            doc = self.get_document(doc_id)
            if doc:
                results[doc_id] = doc
        return results

    def list_document_ids(self) -> List[str]:
        """Lists all document IDs currently in the store."""
        with self._lock:
            return list(self._documents.keys())

# Singleton instance
document_store = DocumentStore()