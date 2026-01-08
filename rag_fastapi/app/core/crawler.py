import httpx
import asyncio
import logging
from urllib.parse import urlparse, urljoin
from typing import Set, List, Optional, Tuple
from datetime import datetime
from bs4 import BeautifulSoup

from app.models.document import Document
from app.config import settings

logger = logging.getLogger(__name__)

class WebCrawler:
    """
    A web crawler to fetch HTML content from specified URLs, respecting
    domain allowlists, max pages, and max depth.
    """
    def __init__(self, user_agent: str, request_timeout: int, max_retries: int):
        self.user_agent = user_agent
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=self.request_timeout,
            follow_redirects=True
        )

    async def _fetch_url(self, url: str, job_id: str) -> Optional[str]:
        """Fetches the content of a single URL with retries."""
        for attempt in range(self.max_retries + 1): # +1 for initial attempt
            try:
                response = await self.client.get(url)
                response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
                logger.info(f"Job {job_id}: Successfully fetched {url} (Attempt {attempt + 1})")
                return response.text
            except httpx.HTTPStatusError as e:
                logger.warning(f"Job {job_id}: HTTP error fetching {url}: {e} (Attempt {attempt + 1})")
            except httpx.RequestError as e:
                logger.warning(f"Job {job_id}: Request error fetching {url}: {e} (Attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Job {job_id}: Unexpected error fetching {url}: {e} (Attempt {attempt + 1})")
            if attempt < self.max_retries: # Only sleep if more retries are coming
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        logger.error(f"Job {job_id}: Failed to fetch {url} after {self.max_retries + 1} attempts. Returning None.")
        return None

    def _get_all_links(self, html_content: str, base_url: str, domain_allowlist: List[str]) -> Set[str]:
        """Extracts all valid links from HTML, filtering by domain allowlist."""
        soup = BeautifulSoup(html_content, 'html.parser')
        links = set()
        initial_link_count = 0
        filtered_link_count = 0

        for a_tag in soup.find_all('a', href=True):
            initial_link_count += 1
            href = a_tag['href']
            full_url = urljoin(base_url, href)
            parsed_url = urlparse(full_url)
            
            if parsed_url.scheme not in ['http', 'https']:
                logger.debug(f"Filtering out non-http(s) link: {full_url}")
                continue
            
            if not any(domain in parsed_url.netloc for domain in domain_allowlist):
                logger.debug(f"Filtering out link not in domain allowlist ({domain_allowlist}): {full_url}")
                continue
            
            clean_url = urljoin(full_url, parsed_url.path)
            if clean_url == base_url:
                logger.debug(f"Filtering out self-referencing base_url: {clean_url}")
                continue
            
            if clean_url:
                links.add(clean_url)
                filtered_link_count += 1
        
        logger.info(f"From {base_url}: Found {initial_link_count} links, {filtered_link_count} unique and allowed links after filtering.")
        return links

    async def crawl(
        self,
        seed_urls: List[str],
        domain_allowlist: List[str],
        max_pages: int,
        max_depth: int,
        job_id: str
    ) -> List[Document]:
        """
        Starts the web crawling process.
        """
        logger.info(f"Job {job_id}: Starting crawl with seed_urls: {seed_urls}, domain_allowlist: {domain_allowlist}, max_pages: {max_pages}, max_depth: {max_depth}")

        visited_urls: Set[str] = set()
        urls_to_visit: List[Tuple[str, int]] = [(url, 0) for url in seed_urls]
        crawled_documents: List[Document] = []

        while urls_to_visit and len(crawled_documents) < max_pages:
            current_url, current_depth = urls_to_visit.pop(0)

            if current_url in visited_urls:
                logger.debug(f"Job {job_id}: Already visited {current_url}. Skipping.")
                continue

            # Check max_pages limit
            if len(crawled_documents) >= max_pages:
                logger.info(f"Job {job_id}: Max pages limit ({max_pages}) reached. Stopping crawl.")
                break
            
            # Check max_depth limit
            if current_depth > max_depth:
                logger.debug(f"Job {job_id}: Max depth limit ({max_depth}) reached for {current_url}. Skipping.")
                continue

            logger.info(f"Job {job_id}: Crawling {current_url} (Depth: {current_depth}, Pages fetched: {len(crawled_documents)}/{max_pages})")
            visited_urls.add(current_url)

            html_content = await self._fetch_url(current_url, job_id)
            if html_content:
                logger.debug(f"Job {job_id}: HTML content fetched for {current_url}. Length: {len(html_content)}.")
                
                # Create a Document object
                doc = Document(
                    url=current_url,
                    html_content=html_content,
                    text_content="", # This will be filled by DocumentProcessor
                    fetch_timestamp=datetime.utcnow(),
                    metadata={}
                )
                crawled_documents.append(doc)
                logger.info(f"Job {job_id}: Document for {current_url} added to crawled_documents. Total: {len(crawled_documents)}")

                # Extract links for further crawling
                if current_depth < max_depth:
                    found_links = self._get_all_links(html_content, current_url, domain_allowlist)
                    logger.info(f"Job {job_id}: Found {len(found_links)} new links from {current_url}.")
                    for link in found_links:
                        if link not in visited_urls and link not in [url for url, _ in urls_to_visit]:
                            urls_to_visit.append((link, current_depth + 1))
                            logger.debug(f"Job {job_id}: Added {link} to URLs to visit.")
            else:
                logger.warning(f"Job {job_id}: No HTML content fetched for {current_url}. Not processing or extracting links.")
            
            logger.debug(f"Job {job_id}: Remaining URLs to visit: {len(urls_to_visit)}")
            await asyncio.sleep(0.1) # Be polite, add a small delay

        logger.info(f"Job {job_id}: Crawling finished. Total pages fetched: {len(crawled_documents)}.")
        return crawled_documents

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()

    async def __aenter__(self):
        return self