import re
from typing import List
import tiktoken
from bs4 import BeautifulSoup
from readability import Document as ReadabilityDocument


def clean_html(html_content: str) -> str:
    """
    Cleans HTML content to extract main text using readability-lxml.
    Removes boilerplate, deduplicates, and collapses whitespace.
    """
    if not html_content:
        return ""

    # Use readability-lxml to get the main content
    doc = ReadabilityDocument(html_content)
    # This gets the HTML of the main body, not just the text
    cleaned_html = doc.summary(html_partial=True)

    # Use BeautifulSoup to convert HTML to clean text
    soup = BeautifulSoup(cleaned_html, 'html.parser')

    # Remove script and style tags
    for script_or_style in soup(['script', 'style']):
        script_or_style.decompose()

    # Get text and replace multiple newlines/spaces with single ones
    text = soup.get_text(" ", strip=True)
    text = re.sub(r'\s+', ' ', text)   # Collapse all whitespace to single spaces
    text = text.strip()

    return text

def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    """
    Splits a long text into smaller chunks for embedding and processing.
    Uses a simple character-based splitting, but attempts to respect sentence boundaries.
    """
    if not text:
        return []

    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_length = 0

    def get_length(segment: str) -> int:
        return len(segment)

    for sentence in sentences:
        sentence_length = get_length(sentence)
        
        # Check if adding the current sentence exceeds chunk_size
        # +1 for potential space between sentences
        if current_length + sentence_length + (len(current_chunk) * 1) <= chunk_size:
            current_chunk.append(sentence)
            current_length += sentence_length + 1
        else:
            if current_chunk:
                chunks.append(" ".join(current_chunk).strip())
            
            # Start a new chunk with overlap
            # Take last 1-2 sentences for overlap, ensuring overlap is within bounds
            overlap_sentences = []
            overlap_length = 0
            for i in range(len(current_chunk) -1, -1, -1):
                s = current_chunk[i]
                if overlap_length + get_length(s) + 1 <= chunk_overlap:
                    overlap_sentences.insert(0, s)
                    overlap_length += get_length(s) + 1
                else:
                    break
            
            current_chunk = overlap_sentences + [sentence]
            current_length = sum(get_length(s) + 1 for s in current_chunk)
            
            # If a single sentence is larger than chunk_size, split it
            while current_length > chunk_size and len(current_chunk) == 1: # Only split if it's a single long sentence
                split_point = sentence.rfind(' ', 0, chunk_size)
                if split_point == -1 or split_point < chunk_size * 0.8: # No space found or too early, force split
                    split_point = chunk_size
                chunks.append(sentence[:split_point].strip())
                sentence = sentence[split_point:].strip()
                current_chunk = [sentence]
                current_length = get_length(sentence)

    if current_chunk:
        chunks.append(" ".join(current_chunk).strip())
            
    return [chunk for chunk in chunks if chunk] # Remove empty chunks

def get_token_count(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    """
    Returns the number of tokens in a text string for a given model.
    """
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base") # Fallback
    
    return len(encoding.encode(text))