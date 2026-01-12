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
=========================================================================================
Sending ingest request to http://localhost:8000/api/ingest with payload: {'seed_urls':                                                                   │
│ ['https://www.goodreads.com/quotes/tag/imagination?author=Albert-Einstein'], 'domain_allowlist': ['goodreads.com'], 'max_pages': 1, 'max_depth': 0,      │
│ 'user_notes': 'Test for Albert Einstein quotes'}                                                                                                         │
│ Ingest job started with ID: dd090e31-a640-47d8-a60a-9ecb28526e69                                                                                         │
│ Polling job status at http://localhost:8000/api/status/dd090e31-a640-47d8-a60a-9ecb28526e69...                                                           │
│ Job dd090e31-a640-47d8-a60a-9ecb28526e69 status: pending                                                                                                 │
│ Job dd090e31-a640-47d8-a60a-9ecb28526e69 status: crawling                                                                                                │
│ Job dd090e31-a640-47d8-a60a-9ecb28526e69 status: completed                                                                                               │
│ Ingestion job dd090e31-a640-47d8-a60a-9ecb28526e69 completed.                                                                                            │
│ Sending ask request to http://localhost:8000/api/ask with payload: {'job_id': 'dd090e31-a640-47d8-a60a-9ecb28526e69', 'question': 'What did Albert       │
│ Einstein say about imagination?'}                                                                                                                        │
│ Ask response: {                                                                                                                                          │
│   "answer": "Albert Einstein said:\n\u201cLogic will get you from A to Z; imagination will get you everywhere.\u201d\n\"It is the preview of life's      │
│ coming attractions.\u201d",                                                                                                                              │
│   "confidence": "high",                                                                                                                                  │
│   "citations": [                                                                                                                                         │
│     {                                                                                                                                                    │
│       "url": "https://www.goodreads.com/quotes/tag/imagination?author=Albert-Einstein",                                                                  │
│       "title": null,                                                                                                                                     │
│       "chunk_id": null,                                                                                                                                  │
│       "quote": "\u201cEverything you can imagine is real.\u201d \u2015 Pablo Picasso \u201cLogic will get you from A to Z; imagination will get you      │
│ everywhere.\u201d \u2015 Albert Einstein \u201cAnyone who lives within their means suffers from a lack of imagination.\u201d \u2015 Oscar Wilde          │
│ \u201cYou never have to change anything you got up in the middle of the night to write.\u201d \u2015 Saul Bellow \u201cStories of imagination tend to    │
│ upset those without one.\u201d \u2015 Terry Pratchett \u201cIf you are a dreamer come in If you are a dreamer a wisher a liar A hoper a pray-er a It is  │
│ the preview of life's coming attractions.\u201d \u2015 Albert Einstein \u201cOur imagination flies -- we are its shadow on the earth.\u201d \u2015       │
│ Vladimir Nabokov \u201cImagination does not become great until human beings, given the courage and the strength, use it to create.\u201d \u2015 Maria    │
│ Montessori \u201cVision is the art of seeing things invisible.\u201d \u2015 Jonathan Swift \u201cImagination is the golden-eyed monster that never       │
│ sleeps. It must be fed; it cannot be ignored.\u201d \u2015 Patricia A. I found out that the more I wrote, the bigger it got.\u201d \u2015 Philip         │
│ Jos\u00e9 Farmer \u201cImagination is everything. Ballard \u201cImagination is the only weapon in the war against reality.\u201d \u2015 Lewis Carroll    │
│ \u201cThere are painters who transform the sun to a yellow spot, but there are others who with the help of their art and their intelligence, transform a │
│ yellow spot into sun\u201d \u2015 Pablo Picasso \u201cImagination will often carry us to worlds that never were, but without it we go nowhere.\u201d     │
│ \u2015 Carl Sagan \u201cA fit, healthy body\u2014that is the best fashion statement\u201d \u2015 Jess C Scott McKillip \u201cI believe in the power of   │
│ the imagination to remake the world, to release the truth within us, to hold back the night, to transcend death, to charm motorways, to ingratiate       │
│ ourselves with birds, to enlist the confidences of madmen.\u201d \u2015 J.G.",                                                                           │
│       "score": null                                                                                                                                      │
│     }                                                                                                                                                    │
│   ],                                                                                                                                                     │
│   "grounding_notes": "Answer generated strictly from retrieved context."                                                                                 │
│ }                                                                                                                                                        │
│ RAG pipeline end-to-end test passed successfully!  
```
