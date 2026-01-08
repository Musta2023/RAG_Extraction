import pytest
from unittest.mock import MagicMock
from app.core.retriever import Retriever
from app.core.embedder import Embedder
from app.services.vector_store import VectorStore
from app.models.document import DocumentChunk
from pydantic import HttpUrl
import numpy as np

@pytest.fixture
def mock_embedder():
    """Mocks the Embedder class."""
    embedder = MagicMock(spec=Embedder)
    embedder.embed_query.return_value = np.array([0.1, 0.2, 0.3], dtype='float32').tolist()
    return embedder

@pytest.fixture
def mock_vector_store():
    """Mocks the VectorStore class."""
    vector_store = MagicMock(spec=VectorStore)
    return vector_store

@pytest.fixture
def retriever(mock_embedder, mock_vector_store):
    """Provides a Retriever instance with mocked dependencies."""
    return Retriever(embedder=mock_embedder, vector_store=mock_vector_store)

@pytest.fixture
def sample_chunks():
    """Provides sample DocumentChunk objects."""
    return [
        DocumentChunk(
            chunk_id="chunk1",
            document_url=HttpUrl("http://example.com/doc1"),
            text_content="This is the first chunk.",
            start_index=0, end_index=20,
            embedding=[0.1, 0.2, 0.3]
        ),
        DocumentChunk(
            chunk_id="chunk2",
            document_url=HttpUrl("http://example.com/doc2"),
            text_content="Second piece of text here.",
            start_index=0, end_index=25,
            embedding=[0.4, 0.5, 0.6]
        ),
        DocumentChunk(
            chunk_id="chunk3",
            document_url=HttpUrl("http://example.com/doc1"),
            text_content="Another part of the first document.",
            start_index=21, end_index=50,
            embedding=[0.7, 0.8, 0.9]
        )
    ]

def test_retrieve_chunks_success(retriever, mock_embedder, mock_vector_store, sample_chunks):
    """Test successful retrieval of chunks."""
    job_id = "test_job"
    query = "test query"
    k = 2

    # Mock vector_store.search to return pre-defined results
    mock_vector_store.search.return_value = [
        (0.05, sample_chunks[0]), # Lower distance means higher relevance
        (0.15, sample_chunks[2])
    ]

    results = retriever.retrieve_chunks(job_id, query, k)

    mock_embedder.embed_query.assert_called_once_with(query)
    mock_vector_store.search.assert_called_once_with(job_id, mock_embedder.embed_query.return_value, k)

    assert len(results) == k
    assert results[0][1].chunk_id == "chunk1"
    assert results[1][1].chunk_id == "chunk3"
    assert results[0][0] < results[1][0] # Ensure sorting by distance (ascending)

def test_retrieve_chunks_no_embedding(retriever, mock_embedder, mock_vector_store):
    """Test retrieval when embedding generation fails."""
    job_id = "test_job"
    query = "test query"
    k = 2

    mock_embedder.embed_query.return_value = [] # Simulate failed embedding

    results = retriever.retrieve_chunks(job_id, query, k)

    mock_embedder.embed_query.assert_called_once_with(query)
    mock_vector_store.search.assert_not_called() # Should not call search if embedding fails
    assert len(results) == 0

def test_retrieve_chunks_no_results_from_vector_store(retriever, mock_embedder, mock_vector_store):
    """Test retrieval when vector store returns no results."""
    job_id = "test_job"
    query = "test query"
    k = 2

    mock_vector_store.search.return_value = [] # Simulate no results

    results = retriever.retrieve_chunks(job_id, query, k)

    mock_embedder.embed_query.assert_called_once_with(query)
    mock_vector_store.search.assert_called_once_with(job_id, mock_embedder.embed_query.return_value, k)
    assert len(results) == 0

def test_retrieve_chunks_exception_handling(retriever, mock_embedder, mock_vector_store):
    """Test retrieval when an exception occurs during search."""
    job_id = "test_job"
    query = "test query"
    k = 2

    mock_vector_store.search.side_effect = Exception("Vector store error")

    results = retriever.retrieve_chunks(job_id, query, k)

    mock_embedder.embed_query.assert_called_once_with(query)
    mock_vector_store.search.assert_called_once_with(job_id, mock_embedder.embed_query.return_value, k)
    assert len(results) == 0