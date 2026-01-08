# RAG FastAPI

This project provides a complete, web-based Retrieval-Augmented Generation (RAG) pipeline using FastAPI. It allows you to ingest web content, index it in a vector store, and ask questions to get evidence-based, citation-backed answers.

## Features

- **Web Crawling**: Ingest content from websites by providing seed URLs.
- **Content Processing**: Cleans HTML, extracts main content, and chunks it into manageable passages.
- **Vector Indexing**: Generates embeddings (using local models, OpenAI, or Gemini) and stores them in a FAISS vector index.
- **Evidence-Based Q&A**: Generates answers strictly from the retrieved content, with citations to the source URLs.
- **Anti-Hallucination**: Designed to minimize LLM hallucination by grounding answers in provided evidence and indicating confidence levels.
- **Async Ingestion**: Crawling and indexing are handled as background tasks.
- **Dockerized**: Comes with `Dockerfile` and `docker-compose.yml` for easy setup and deployment.
- **Configurable**: Easily configure models, API keys, and other settings via environment variables.

## Project Structure

```
├───app/                # Main application code
│   ├───api/            # FastAPI routers (endpoints)
│   ├───background/     # Background task definitions (Celery)
│   ├───core/           # Core RAG pipeline logic (crawl, process, index, answer)
│   ├───models/         # Pydantic schemas and data models
│   ├───services/       # Services for vector stores, job tracking, etc.
│   └───utils/          # Utility modules (logging, etc.)
├───data/               # Persistent data (vector indexes, etc.)
├───docs/               # Project documentation
├───evaluation/         # Scripts for evaluating pipeline performance
├───logs/               # Application logs
├───tests/              # Unit and integration tests
├───.env.example        # Example environment variables
├───docker-compose.yml  # Docker Compose setup
├───Dockerfile          # Application Dockerfile
└───requirements.txt    # Python dependencies
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.9+ (for local development)
- An environment file (copy `.env.example` to `.env`)

### Installation & Running with Docker

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-repo/rag-fastapi.git
    cd rag-fastapi
    ```

2.  **Configure your environment:**
    - Copy the example environment file: `cp .env.example .env`
    - Edit the `.env` file to add your API keys (e.g., `OPENAI_API_KEY`) and adjust settings as needed.

3.  **Build and run the services:**
    ```bash
    docker-compose up --build
    ```
    This will start the FastAPI web server, a Celery worker for background tasks, and a Redis instance for message queuing. The API will be available at `http://localhost:8000`.

### Local Development (Without Docker)

1.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure your environment:**
    - Copy the example environment file: `cp .env.example .env`
    - Edit the `.env` file.

4.  **Run the application:**
    ```bash
    uvicorn app.main:app --reload
    ```

## API Endpoints

The API documentation is available at `http://localhost:8000/docs` when the server is running.

### 1. Start Ingestion

- **Endpoint**: `POST /ingest`
- **Description**: Starts a background job to crawl and index content from a list of seed URLs.
- **Body**:
  ```json
  {
    "seed_urls": ["https://example.com/blog"],
    "domain_allowlist": ["example.com"],
    "max_pages": 20,
    "max_depth": 2,
    "user_notes": "Initial ingestion of the company blog."
  }
  ```
- **Response**:
  ```json
  {
    "job_id": "some-unique-job-id",
    "message": "Ingestion job started."
  }
  ```

### 2. Get Ingestion Status

- **Endpoint**: `GET /status/{job_id}`
- **Description**: Retrieves the status of a specific ingestion job.
- **Response**:
  ```json
  {
    "job_id": "some-unique-job-id",
    "status": "completed",
    "pages_fetched": 15,
    "pages_indexed": 15,
    "errors": [],
    "started_at": "...",
    "completed_at": "..."
  }
  ```

### 3. Ask a Question

- **Endpoint**: `POST /ask`
- **Description**: Ask a question against the indexed content of a completed job.
- **Body**:
  ```json
  {
    "job_id": "some-unique-job-id",
    "question": "What are the key features of product X?"
  }
  ```
- **Response**:
  ```json
  {
    "answer": "The key features of product X are A, B, and C.",
    "confidence": "high",
    "citations": [
      {
        "url": "https://example.com/blog/product-x",
        "title": "Introducing Product X",
        "chunk_id": "chunk-123",
        "quote": "Product X includes key features such as A, B, and C...",
        "score": 0.91
      }
    ],
    "grounding_notes": "The answer was synthesized from one high-confidence source."
  }
  ```

### 4. Health Check

- **Endpoint**: `GET /health`
- **Description**: Returns a `200 OK` status if the service is running.
- **Response**:
  ```json
  {
    "status": "ok"
  }
  ```

## Configuration

The application is configured via environment variables defined in the `.env` file.

| Variable                  | Description                                                              | Default              |
| ------------------------- | ------------------------------------------------------------------------ | -------------------- |
| `LLM_PROVIDER`            | The provider for embeddings and generation (`openai`, `gemini`, `local`).  | `openai`             |
| `OPENAI_API_KEY`          | Your OpenAI API key.                                                     | `your_openai_api_key`|
| `OPENAI_EMBEDDING_MODEL`  | The model for generating embeddings.                                     | `text-embedding-3-small`|
| `OPENAI_GENERATION_MODEL` | The model for generating answers.                                        | `gpt-3.5-turbo`      |
| `VECTOR_STORE_PATH`       | Directory to persist the FAISS index and related data.                   | `./.vector_store`    |
| `CRAWLER_USER_AGENT`      | User agent string for the web crawler.                                   | (See `.env.example`) |
| `RATE_LIMIT_REQUESTS`     | Number of requests allowed per `RATE_LIMIT_TIMESCALE`.                   | `100`                |
| `RATE_LIMIT_TIMESCALE`    | Timescale for rate limiting (`minute`, `hour`).                          | `minute`             |


## Running Tests

To run the unit tests, use `pytest`:

```bash
pytest
```