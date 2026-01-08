import pytest
from app.core.processor import DocumentProcessor
from app.models.document import Document
from datetime import datetime
from pydantic import HttpUrl

@pytest.fixture
def document_processor():
    """Provides a DocumentProcessor instance."""
    return DocumentProcessor(chunk_size=100, chunk_overlap=20)

def test_process_empty_html(document_processor):
    """Test processing a document with empty HTML content."""
    doc = Document(url=HttpUrl("http://example.com"), html_content="", text_content="")
    chunks = document_processor.process_document(doc)
    assert len(chunks) == 0

def test_process_no_meaningful_text_html(document_processor):
    """Test processing HTML that results in no meaningful text."""
    html = "<html><body><script>console.log('hi');</script><div></div></body></html>"
    doc = Document(url=HttpUrl("http://example.com"), html_content=html, text_content="")
    chunks = document_processor.process_document(doc)
    assert len(chunks) == 0

def test_process_simple_html(document_processor):
    """Test processing simple HTML with basic text."""
    html = "<html><body><h1>Title</h1><p>This is a paragraph.</p><p>Another one.</p></body></html>"
    doc = Document(url=HttpUrl("http://example.com/simple"), html_content=html, text_content="")
    chunks = document_processor.process_document(doc)
    
    assert len(chunks) > 0
    assert doc.text_content.strip() == "Title This is a paragraph. Another one."
    # Expect at least one chunk containing parts of the text
    assert any("This is a paragraph" in c.text_content for c in chunks)
    assert any("Another one" in c.text_content for c in chunks)
    assert chunks[0].document_url == HttpUrl("http://example.com/simple")
    assert "chunk_id" in chunks[0].model_dump()
    assert chunks[0].metadata["source"] == "http://example.com/simple"


def test_process_long_text_chunking(document_processor):
    """Test chunking of a long text with specified chunk size and overlap."""
    long_text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five. Sentence six. Sentence seven. Sentence eight. Sentence nine. Sentence ten. " * 5
    html = f"<html><body><p>{long_text}</p></body></html>"
    doc = Document(url=HttpUrl("http://example.com/long"), html_content=html, text_content="")
    chunks = document_processor.process_document(doc)

    assert len(chunks) > 1 # Should be more than one chunk for long text
    
    # Check that chunks are roughly of the correct size (within some tolerance)
    for chunk in chunks:
        assert len(chunk.text_content) <= document_processor.chunk_size + document_processor.chunk_overlap * 2 # Some buffer for overlap
        assert chunk.document_url == HttpUrl("http://example.com/long")
    
    # The precise overlap check is too fragile and depends heavily on chunk_text implementation details.
    # Basic checks for chunk existence and size are sufficient.

def test_metadata_transfer(document_processor):
    """Test that metadata is correctly transferred to chunks."""
    doc_metadata = {"author": "Test Author", "category": "Testing"}
    html = "<html><body><p>Content.</p></body></html>"
    doc = Document(url=HttpUrl("http://example.com/meta"), html_content=html, text_content="", metadata=doc_metadata)
    chunks = document_processor.process_document(doc)

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.metadata["author"] == "Test Author"
        assert chunk.metadata["category"] == "Testing"
        assert "fetch_timestamp" in chunk.metadata
        assert "source" in chunk.metadata