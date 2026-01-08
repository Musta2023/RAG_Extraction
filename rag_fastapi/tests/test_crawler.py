import pytest
import httpx
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.core.crawler import WebCrawler
from app.models.document import Document
from app.config import settings
from datetime import datetime # Import datetime

@pytest.fixture
def mock_httpx_client():
    """Mocks httpx.AsyncClient for WebCrawler."""
    with patch('httpx.AsyncClient') as MockAsyncClient:
        mock_instance = MockAsyncClient.return_value
        mock_instance.get = AsyncMock()
        yield mock_instance

@pytest.fixture
def crawler(mock_httpx_client):
    """Provides a WebCrawler instance with a mocked httpx client."""
    return WebCrawler(
        user_agent=settings.CRAWLER_USER_AGENT,
        request_timeout=settings.CRAWLER_REQUEST_TIMEOUT,
        max_retries=settings.CRAWLER_MAX_RETRIES
    )

@pytest.mark.asyncio
async def test_fetch_url_success(crawler, mock_httpx_client):
    """Test successful URL fetching."""
    mock_httpx_client.get.return_value = MagicMock(text="<html>Test</html>", status_code=200, raise_for_status=lambda: None)
    
    content = await crawler._fetch_url("http://example.com/page1", "job123")
    assert content == "<html>Test</html>"
    mock_httpx_client.get.assert_called_once_with("http://example.com/page1")

@pytest.mark.asyncio
async def test_fetch_url_http_error(crawler, mock_httpx_client):
    """Test URL fetching with HTTP error and retries."""
    mock_httpx_client.get.side_effect = [
        httpx.HTTPStatusError(message="Not Found", request=httpx.Request("GET", "http://example.com"), response=httpx.Response(404))
        for _ in range(settings.CRAWLER_MAX_RETRIES + 1) # +1 for initial attempt
    ]
    
    content = await crawler._fetch_url("http://example.com/page1", "job123")
    assert content is None
    # Should attempt max_retries + 1 (initial + retries)
    assert mock_httpx_client.get.call_count == settings.CRAWLER_MAX_RETRIES + 1

@pytest.mark.asyncio
async def test_fetch_url_request_error(crawler, mock_httpx_client):
    """Test URL fetching with request error and retries."""
    mock_httpx_client.get.side_effect = [
        httpx.RequestError("Connection Error", request=httpx.Request("GET", "http://example.com"))
        for _ in range(settings.CRAWLER_MAX_RETRIES + 1) # +1 for initial attempt
    ]
    
    content = await crawler._fetch_url("http://example.com/page1", "job123")
    assert content is None
    assert mock_httpx_client.get.call_count == settings.CRAWLER_MAX_RETRIES + 1

def test_get_all_links(crawler):
    """Test link extraction and filtering."""
    html = """
    <html>
        <body>
            <a href="/">Home</a>
            <a href="/about">About</a>
            <a href="http://example.com/contact">Contact</a>
            <a href="https://other.com/external">External</a>
            <a href="#section">Internal Link</a>
            <a href="ftp://files.com/doc.pdf">FTP Link</a>
        </body>
    </html>
    """
    base_url = "http://example.com/"
    domain_allowlist = ["example.com"]
    
    links = crawler._get_all_links(html, base_url, domain_allowlist)
    # The base_url itself should not be considered a found link from content if href is "/"
    expected_links = {"http://example.com/about", "http://example.com/contact"}
    assert links == expected_links

@pytest.mark.asyncio
async def test_crawl_single_page(crawler, mock_httpx_client):
    """Test crawling a single page without following links."""
    mock_httpx_client.get.return_value = MagicMock(
        text="<html><body>Hello World!</body></html>", status_code=200, raise_for_status=lambda: None
    )
    
    seed_urls = ["http://example.com/start"]
    domain_allowlist = ["example.com"]
    max_pages = 1
    max_depth = 0
    job_id = "job1"

    documents = await crawler.crawl(seed_urls, domain_allowlist, max_pages, max_depth, job_id)
    
    assert len(documents) == 1
    assert str(documents[0].url) == "http://example.com/start" # Convert HttpUrl to string for comparison
    assert documents[0].html_content == "<html><body>Hello World!</body></html>"
    mock_httpx_client.get.assert_called_once()

@pytest.mark.asyncio
async def test_crawl_multi_page_depth_limit(crawler, mock_httpx_client):
    """Test crawling multiple pages with a depth limit."""
    
    # Mock responses for different URLs
    def mock_get(url, **kwargs):
        resp = MagicMock(status_code=200, raise_for_status=lambda: None)
        if url == "http://example.com/page1":
            resp.text = '<html><a href="/page2">Page 2</a><a href="http://other.com/page">External</a></html>'
        elif url == "http://example.com/page2":
            resp.text = '<html><a href="/page3">Page 3</a></html>'
        elif url == "http://example.com/page3":
            resp.text = '<html>Final Page</html>'
        else:
            raise httpx.RequestError("Unknown URL", request=httpx.Request("GET", url))
        return resp

    mock_httpx_client.get.side_effect = mock_get

    seed_urls = ["http://example.com/page1"]
    domain_allowlist = ["example.com"]
    max_pages = 5
    max_depth = 1 # Only page1 and page2 should be crawled
    job_id = "job2"

    documents = await crawler.crawl(seed_urls, domain_allowlist, max_pages, max_depth, job_id)
    
    assert len(documents) == 2
    urls = {str(doc.url) for doc in documents} # Convert HttpUrl to string for set comparison
    assert "http://example.com/page1" in urls
    assert "http://example.com/page2" in urls
    assert "http://example.com/page3" not in urls # max_depth = 1 means only depth 0 and 1
    
    assert mock_httpx_client.get.call_count == 2 # page1 and page2 fetched

@pytest.mark.asyncio
async def test_crawl_max_pages_limit(crawler, mock_httpx_client):
    """Test crawling stops at max_pages limit."""
    
    page_count = 0
    def mock_get_pages(url, **kwargs):
        nonlocal page_count
        page_count += 1
        resp = MagicMock(status_code=200, raise_for_status=lambda: None)
        resp.text = f'<html>Page {page_count} <a href="/page{page_count + 1}">Next</a></html>'
        return resp

    mock_httpx_client.get.side_effect = mock_get_pages

    seed_urls = ["http://example.com/page1"]
    domain_allowlist = ["example.com"]
    max_pages = 3
    max_depth = 5
    job_id = "job3"

    documents = await crawler.crawl(seed_urls, domain_allowlist, max_pages, max_depth, job_id)
    
    assert len(documents) == 3
    urls = {str(doc.url) for doc in documents} # Convert HttpUrl to string for set comparison
    assert "http://example.com/page1" in urls
    assert "http://example.com/page2" in urls
    assert "http://example.com/page3" in urls
    assert mock_httpx_client.get.call_count == 3 # Only 3 pages should be fetched