# RAG FastAPI: Design Notes

This document outlines the design philosophy, architectural choices, and trade-offs made during the development of the RAG FastAPI project.

## 1. Core Philosophy

The primary goal is to create a **reliable, evidence-based question-answering system** that minimizes LLM hallucination. The system is designed to be a modular, scalable, and easy-to-deploy FastAPI application. Key principles include:

- **Strictly Grounded Generation**: Answers must be synthesized *only* from the text chunks retrieved from the vector store. The LLM's internal knowledge should not be used.
- **Transparency and Citations**: Every factual claim in an answer must be backed by a precise citation, linking back to the source document and quoting the relevant text.
- **Confidence Scoring**: The system should be able to assess its own confidence in an answer based on the quality and relevance of the retrieved evidence.
- **Developer Experience**: The project should be easy to set up, configure, and extend, with clear documentation and a logical structure.

## 2. Architectural Choices

### 2.1. FastAPI Framework

- **Why FastAPI?**: FastAPI was chosen for its high performance, asynchronous support (crucial for I/O-bound tasks like web crawling and model interaction), automatic data validation with Pydantic, and interactive API documentation (Swagger/ReDoc).

### 2.2. Asynchronous Ingestion (Celery + Redis)

- **The Challenge**: Web crawling and document processing can be very time-consuming. Running this on the main API request thread would lead to timeouts and a poor user experience.
- **The Solution**: We use a background task processing system.
    - **Celery**: A robust and widely-used distributed task queue. It allows us to offload the `ingest` pipeline to a separate worker process, immediately returning a `job_id` to the user.
    - **Redis**: Acts as the message broker for Celery, managing the queue of tasks to be executed. It's also used as a simple key-value store to track the status of each job.
- **Trade-offs**:
    - **Pros**: Highly scalable. Decouples the API from the heavy lifting of ingestion. Provides reliability and retry mechanisms.
    - **Cons**: Adds complexity to the stack (requires running Redis and a Celery worker). For very simple use cases, FastAPI's built-in `BackgroundTasks` might suffice, but Celery offers better scalability and visibility.

### 2.3. RAG Pipeline Components

- **Fetcher (`httpx`)**:
    - `httpx` is a modern, async-first HTTP client for Python. It's used over `requests` to avoid blocking the event loop during web crawling.
    - It's configured with a polite user agent, reasonable timeouts, and a simple retry mechanism to handle transient network issues.

- **Cleaner (`BeautifulSoup` + `readability-lxml`)**:
    - `BeautifulSoup` is a standard for parsing HTML.
    - `readability-lxml` is a Python port of Mozilla's Readability.js, which is excellent at extracting the core "article" text from a webpage, stripping away ads, navigation bars, and other boilerplate. This is a crucial step for improving the signal-to-noise ratio of the content that gets indexed.

- **Indexer (Pluggable Embedders + FAISS)**:
    - **Embedders**: The system is designed to be model-agnostic. A simple factory pattern in `app/core/embedder.py` allows switching between OpenAI, Gemini, and local Sentence Transformer models via an environment variable (`LLM_PROVIDER`). This provides flexibility based on cost, performance, and privacy requirements.
    - **Vector Store (`FAISS`)**: FAISS (Facebook AI Similarity Search) was chosen as the initial vector store.
        - **Pros**: Extremely fast for in-memory similarity search, easy to set up (`faiss-cpu`), and sufficient for many small-to-medium scale projects. The index can be easily persisted to disk.
        - **Cons**: Not a managed, distributed database. Doesn't inherently support metadata filtering or real-time updates as elegantly as solutions like `pgvector` or managed vector databases. For this project, we store metadata separately in a simple file-based document store.
    - **Alternative Considered (`pgvector`)**: Using PostgreSQL with the `pgvector` extension would allow storing embeddings and metadata in the same place and leveraging SQL for metadata filtering. This would be a better choice for larger-scale applications requiring more complex queries, but adds the overhead of managing a PostgreSQL database.

- **Answer Generator (LLM with a Grounding Prompt)**:
    - **The Prompt is Key**: The core of the anti-hallucination strategy lies in the prompt sent to the LLM. The prompt explicitly instructs the model:
        1. To answer the user's question *based solely* on the provided context chunks.
        2. To generate citations for every piece of information.
        3. To abstain if the context does not contain the answer.
    - **Self-Correction (Post-Processing)**: A planned enhancement is a post-generation check. This step would involve a second, simpler LLM call (or a rule-based system) to verify that the claims in the generated answer are actually supported by the cited quotes.

## 3. Anti-Hallucination Strategy

This is the most critical aspect of the project's design. The strategy is multi-layered:

1.  **High-Quality Input**: Garbage in, garbage out. By using `readability-lxml` to get clean, relevant text, we reduce the amount of noise the retriever and generator have to deal with.
2.  **Precise Retrieval**: The quality of the retrieved chunks is paramount. Using a strong embedding model and a fast vector index ensures the context passed to the LLM is as relevant as possible.
3.  **Strictly Grounded Prompting**: As discussed above, the prompt engineers the LLM to act as a "summarizer of provided facts" rather than a "knowledgeable answerer."
4.  **Mandatory Citations**: Forcing the model to cite its sources makes it less likely to invent information, as it has to point to the origin of its claims.
5.  **Confidence Score**: The confidence score is not a direct output of the LLM. It's calculated based on heuristics from the retrieval step, such as the similarity scores of the top retrieved chunks. For example:
    - **High**: Multiple chunks with high similarity scores (>0.85) are found.
    - **Medium**: Fewer chunks, or chunks with middling scores (0.75-0.85) are found.
    - **Low**: Only a few chunks with low similarity scores (<0.75) are found, or the content seems contradictory.

## 4. Future Improvements

- **Managed Vector Database**: Replace FAISS with a managed service (Pinecone, Weaviate) or a more robust self-hosted solution (`pgvector`) to improve scalability and metadata handling.
- **Advanced Chunking**: Implement more sophisticated chunking strategies (e.g., content-aware chunking based on HTML structure or sentence semantics) to improve context quality.
- **Answer Self-Correction**: Implement a post-generation validation step to programmatically check for unsupported claims in the final answer.
- **More Sophisticated Job Management**: The current in-memory/Redis job tracking is simple. For production, persisting job metadata to a proper database (like PostgreSQL or SQLite) would be more robust.
