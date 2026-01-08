import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # App
    APP_NAME: str = "RAG FastAPI"
    APP_VERSION: str = "0.1.0"
    LOG_LEVEL: str = "DEBUG"
    API_PREFIX: str = "/api"

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_TIMESCALE: str = "minute"
    
    # CORS
    CLIENT_ORIGIN: str = ""

    # LLM and Embedding Providers
    LLM_PROVIDER: str = "gemini"
    EMBEDDING_PROVIDER: str = "local"

    # OpenAI
    OPENAI_API_KEY: str = "your_openai_api_key"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_GENERATION_MODEL: str = "gpt-3.5-turbo"

    # Gemini
    GEMINI_API_KEY: str = "your_gemini_api_key"
    GEMINI_EMBEDDING_MODEL: str = "models/embedding-001"
    GEMINI_GENERATION_MODEL: str = "models/gemini-pro"

    # Local SentenceTransformer
    LOCAL_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    # Vector Store
    VECTOR_STORE_PATH: str = "./.vector_store"
    DOCUMENT_STORE_PATH: str = "./.document_store"

    # Crawler
    CRAWLER_USER_AGENT: str = "Mozilla/5.0 (compatible; RAGFastAPIBot/0.1)"
    CRAWLER_REQUEST_TIMEOUT: int = 10
    CRAWLER_MAX_RETRIES: int = 3

    # Retriever
    RETRIEVER_TOP_K: int = 5 # Number of top chunks to retrieve

    # FAISS Indexing
    FAISS_BATCH_SIZE: int = 1000 # Batch size for adding chunks to FAISS

    # Logging
    LOG_PATH: str = "logs/"

    # Celery & Redis
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

    # Watchdog for stuck jobs
    WATCHDOG_INTERVAL_SECONDS: int = 300 # How often the watchdog runs (5 minutes)
    WATCHDOG_THRESHOLD_SECONDS: int = 600 # How long a job can be inactive before watchdog marks it failed (10 minutes)

    # Celery Task Time Limits
    CELERY_SOFT_TIME_LIMIT: int = 600 # Soft time limit for ingestion tasks (10 minutes)
    CELERY_HARD_TIME_LIMIT: int = 1200 # Hard time limit for ingestion tasks (20 minutes)

    class Config:
        case_sensitive = True

# Instantiate settings
settings = Settings()
