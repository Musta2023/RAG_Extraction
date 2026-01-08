import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import numpy as np

from app.config import settings
from app.utils.text_utils import get_token_count

logger = logging.getLogger(__name__)

# --- Abstract Base Class for Embedders ---

class BaseEmbedder(ABC):
    """
    Abstract base class for all embedder implementations.
    """
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        pass

# --- OpenAI Embedder Implementation ---

class OpenAIEmbedder(BaseEmbedder):
    def __init__(self):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Please install openai: pip install openai")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_EMBEDDING_MODEL
        logger.info(f"Initialized OpenAIEmbedder: {self.model}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not settings.OPENAI_API_KEY:
            logger.error("OpenAI API key missing.")
            return [[] for _ in texts]
        try:
            response = self.client.embeddings.create(input=texts, model=self.model)
            return [d.embedding for d in response.data]
        except Exception as e:
            logger.error(f"OpenAI Embedding error: {e}")
            return [[] for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        results = self.embed_documents([text])
        return results[0] if results else []

# --- Google Gemini Embedder Implementation ---

class GeminiEmbedder(BaseEmbedder):
    """
    FIXED: Uses google-generativeai (the correct library for .configure())
    """
    def __init__(self):
        try:
            # IMPORTANT: Ensure 'google-generativeai' is in requirements.txt, NOT 'google-genai'
            import google.generativeai as genai 
        except ImportError:
            raise ImportError("Please install google-generativeai: pip install google-generativeai")
            
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key":
            logger.error("Gemini API key is not set.")
            self.model = None
        else:
            self.genai = genai
            self.genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = settings.GEMINI_EMBEDDING_MODEL
            # Default dimension for models/embedding-001 is 768
            self.dimension = 768 
            logger.info(f"Initialized GeminiEmbedder: {self.model}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not self.model:
            return [[] for _ in texts]
        try:
            # Gemini batch embedding
            response = self.genai.embed_content(
                model=self.model, 
                content=texts, 
                task_type="RETRIEVAL_DOCUMENT"
            )
            
            # Gemini returns a dict with a list of embeddings
            embeddings = response.get('embedding', [])
            
            # Ensure every element is a list of Python floats (not numpy/tensors)
            if isinstance(embeddings, np.ndarray):
                embeddings = embeddings.tolist()
            
            return embeddings
        except Exception as e:
            logger.error(f"Gemini Embedding error: {e}")
            return [[] for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        try:
            response = self.genai.embed_content(
                model=self.model, 
                content=text, 
                task_type="RETRIEVAL_QUERY"
            )
            embedding = response.get('embedding', [])
            return embedding
        except Exception as e:
            logger.error(f"Gemini Query error: {e}")
            return []

# --- Local Sentence Transformer Embedder Implementation ---

class LocalSentenceTransformerEmbedder(BaseEmbedder):
    """
    FIXED: Converts Tensors/Numpy to List[float] to prevent "Replaced with zeros" bug.
    """
    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError("Please install sentence-transformers: pip install sentence-transformers")
            
        self.model_name = settings.LOCAL_EMBEDDING_MODEL
        # Use CPU for Docker unless GPU is explicitly configured
        self.model = SentenceTransformer(self.model_name, device="cpu")
        self.embedding_dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Initialized LocalEmbedder: {self.model_name} (Dim: {self.embedding_dimension})")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            # Generate embeddings (returns numpy array by default)
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            
            # CRITICAL FIX: Convert Numpy array to Python List of Lists.
            # This converts np.float32 to standard Python floats, 
            # which passes your validation and works with FAISS/JSON.
            embeddings_list = embeddings.tolist()
            
            processed_embeddings = []
            for i, emb in enumerate(embeddings_list):
                if len(emb) != self.embedding_dimension:
                    logger.warning(f"Embedding {i} dimension mismatch. Expected {self.embedding_dimension}, got {len(emb)}. Using zeros.")
                    processed_embeddings.append([0.0] * self.embedding_dimension)
                else:
                    processed_embeddings.append(emb)

            return processed_embeddings
        except Exception as e:
            logger.error(f"Local Embedding error: {e}")
            return [[0.0] * self.embedding_dimension for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Local Query error: {e}")
            return [0.0] * self.embedding_dimension

# --- Embedder Factory ---

class Embedder:
    """
    Factory class to provide the correct embedder instance based on settings.
    """
    def __init__(self):
        self._embedder_instance: Optional[BaseEmbedder] = None
        self._initialize_embedder()

    def _initialize_embedder(self):
        provider = settings.EMBEDDING_PROVIDER.lower()
        if provider == "openai":
            self._embedder_instance = OpenAIEmbedder()
        elif provider == "gemini":
            self._embedder_instance = GeminiEmbedder()
        elif provider == "local":
            self._embedder_instance = LocalSentenceTransformerEmbedder()
        else:
            raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER}")
        logger.info(f"Active Embedder Factory initialized: {provider}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not self._embedder_instance:
            self._initialize_embedder()
        return self._embedder_instance.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        if not self._embedder_instance:
            self._initialize_embedder()
        return self._embedder_instance.embed_query(text)
