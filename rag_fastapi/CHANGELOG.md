# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-05

### Added

- Initial release of the RAG FastAPI project.
- **API Endpoints**:
    - `POST /ingest`: Asynchronously crawls and indexes web content.
    - `GET /status/{job_id}`: Checks the status of an ingestion job.
    - `POST /ask`: Asks a question and receives an evidence-based answer.
    - `GET /health`: Basic health check.
- **RAG Pipeline**:
    - Web crawling via `httpx`.
    - HTML cleaning with `BeautifulSoup` and `readability-lxml`.
    - Text chunking and metadata association.
    - Pluggable embedding models (OpenAI, Gemini, local Sentence Transformers).
    - Vector indexing using `faiss-cpu`.
    - Grounded answer generation with citations.
- **Engineering**:
    - Background task processing with Celery and Redis.
    - Docker and Docker Compose for containerized deployment.
    - Configuration via environment variables (`.env`).
    - Structured JSON logging.
    - Basic API rate limiting.
- **Documentation**:
    - `README.md` with setup 
    
    
    and usage instructions.
    - `design_note.md` explaining architectural choices.
- **Testing**:
    - Initial unit tests for API endpoints and core components.
    - Evaluation script for sample Q&A.
