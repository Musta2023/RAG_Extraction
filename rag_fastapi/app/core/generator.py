import logging
from typing import List, Tuple, Dict, Any, Optional
from abc import ABC, abstractmethod
from app.config import settings
from app.models.document import DocumentChunk
from app.models.schemas import Citation

logger = logging.getLogger(__name__)

# --- Abstract Base Class for Generators ---

class BaseGenerator(object):
    """
    Abstract base class for all answer generation implementations.
    """
    def __init__(self):
        # Placeholder for model initialization in concrete classes
        pass

    def _format_context(self, retrieved_chunks: List[Tuple[float, DocumentChunk]]) -> str:
        """
        Formats the retrieved chunks into a string that can be used as context
        for the LLM.
        """
        formatted_context = ""
        for i, (score, chunk) in enumerate(retrieved_chunks):
            # Include score in context for LLM to potentially use for confidence
            formatted_context += f"--- Source {i+1} (Score: {score:.2f}, URL: {chunk.document_url}) ---\n"
            formatted_context += chunk.text_content + "\n\n"
        return formatted_context.strip()

    def _generate_citations(self, answer: str, retrieved_chunks: List[Tuple[float, DocumentChunk]]) -> List[Citation]:
        """
        Analyzes the generated answer and the retrieved chunks to identify and
        create citations. This is a heuristic-based approach.
        A more advanced implementation might use LLM to extract direct quotes and their sources.
        """
        citations = []
        # Simple heuristic: if a chunk's content is implicitly used, cite it.
        # This can be improved by checking for exact phrase matches or using LLM for citation extraction.
        cited_urls = set()
        for score, chunk in retrieved_chunks:
            if str(chunk.document_url) not in cited_urls and any(word in answer for word in chunk.text_content.split()[:10]):
                citations.append(Citation(
                    url=chunk.document_url,
                    title=chunk.document_title,
                    chunk_id=chunk.chunk_id,
                    quote=chunk.text_content[:100] + "..." if len(chunk.text_content) > 100 else chunk.text_content, # Short quote
                    score=score
                ))
                cited_urls.add(str(chunk.document_url))
        return citations

    def _assess_confidence(self, retrieved_chunks: List[Tuple[float, DocumentChunk]]) -> str:
        """
        Assesses the confidence level based on the quality of retrieved chunks.
        Heuristic: depends on the number and scores of the top-k chunks.
        """
        if not retrieved_chunks:
            return "low"

        top_scores = [score for score, _ in retrieved_chunks]
        avg_top_score = sum(top_scores) / len(top_scores) if top_scores else 0.0

        if avg_top_score > 0.8 and len(retrieved_chunks) >= 3:
            return "high"
        elif avg_top_score > 0.6 and len(retrieved_chunks) >= 1:
            return "medium"
        else:
            return "low"
    
    @abstractmethod
    def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[Tuple[float, DocumentChunk]],
        job_id: str
    ) -> Dict[str, Any]:
        """
        Generates an answer based on the question and retrieved chunks.
        Must return answer, confidence, citations, and grounding_notes.
        """
        pass

# --- OpenAI Generator Implementation ---

class OpenAIGenerator(BaseGenerator):
    """
    Answer generator using OpenAI's chat models.
    """
    def __init__(self):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "The 'openai' package is not installed. "
                "Please install it with 'pip install openai'"
            )
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_GENERATION_MODEL
        logger.info(f"Initialized OpenAIGenerator with model: {self.model}")

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[Tuple[float, DocumentChunk]],
        job_id: str
    ) -> Dict[str, Any]:
        if not retrieved_chunks:
            return {
                "answer": "I cannot answer this question as no relevant information was found.",
                "confidence": "low",
                "citations": [],
                "grounding_notes": "No relevant documents were retrieved."
            }

        context = self._format_context(retrieved_chunks)
        
        # Crafting a strong prompt for grounded generation
        system_prompt = (
            "You are a helpful and honest assistant. Your task is to answer the user's question "
            "STRICTLY based on the provided context. "
            "If the answer is not available in the context, clearly state 'I cannot answer this question based on the provided information.' "
            "Do not use any prior knowledge. "
            "For each statement you make, explicitly refer to the source document by its number (e.g., [Source 1]). "
            "Try to make the answer concise and to the point. "
            "Ensure that every piece of information in your answer can be traced back to the context."
        )

        user_prompt = (
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer:"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0, # Aim for factual, not creative
                max_tokens=500 # Limit response length
            )
            answer_text = response.choices[0].message.content.strip()
            
            citations = self._generate_citations(answer_text, retrieved_chunks)
            confidence = self._assess_confidence(retrieved_chunks)

            return {
                "answer": answer_text,
                "confidence": confidence,
                "citations": citations,
                "grounding_notes": "Answer generated from retrieved documents using OpenAI."
            }
        except Exception as e:
            logger.error(f"Error generating answer with OpenAI for job {job_id}, question '{question}': {e}")
            return {
                "answer": "An error occurred while generating the answer.",
                "confidence": "low",
                "citations": [],
                "grounding_notes": f"Error: {e}"
            }

# --- Google Gemini Generator Implementation ---

class GeminiGenerator(BaseGenerator):
    """
    Answer generator using Google's Gemini chat models.
    """
    def __init__(self):
        try:
            import google.genai as genai
        except ImportError:
            raise ImportError(
                "The 'google-genai' package is not installed. "
                "Please install it with 'pip install google-genai'"
            )
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key":
            logger.error("Gemini API key is not set. Cannot initialize Gemini Generator.")
            self.model = None
        else:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self.model_name = settings.GEMINI_GENERATION_MODEL
            logger.info(f"Initialized GeminiGenerator with model: {self.model_name}")

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[Tuple[float, DocumentChunk]],
        job_id: str
    ) -> Dict[str, Any]:
        if not retrieved_chunks:
            return {
                "answer": "I cannot answer this question as no relevant information was found.",
                "confidence": "low",
                "citations": [],
                "grounding_notes": "No relevant documents were retrieved."
            }
        
        context = self._format_context(retrieved_chunks)

        # Gemini uses a slightly different message structure
        messages = [
            {"role": "user", "parts": [
                "You are a helpful and honest assistant. Your task is to answer the user's question "
                "STRICTLY based on the provided context. "
                "If the answer is not available in the context, clearly state 'I cannot answer this question based on the provided information.' "
                "Do not use any prior knowledge. "
                "For each statement you make, explicitly refer to the source document by its number (e.g., [Source 1]). "
                "Try to make the answer concise and to the point. "
                "Ensure that every piece of information in your answer can be traced back to the context."
            ]},
            {"role": "model", "parts": ["Understood. I will provide answers strictly based on the context and cite my sources."]},
            {"role": "user", "parts": [
                f"Context:\n{context}\n\n"
                f"Question: {question}\n\n"
                "Answer:"
            ]}
        ]

        try:
            model_instance = self.client.get_model(self.model_name)
            response = model_instance.generate_content(messages, safety_settings={'HARASSMENT': 'BLOCK_NONE'})
            
            answer_text = response.text.strip()
            
            citations = self._generate_citations(answer_text, retrieved_chunks)
            confidence = self._assess_confidence(retrieved_chunks)

            return {
                "answer": answer_text,
                "confidence": confidence,
                "citations": citations,
                "grounding_notes": "Answer generated from retrieved documents using Gemini."
            }
        except Exception as e:
            logger.error(f"Error generating answer with Gemini for job {job_id}, question '{question}': {e}")
            return {
                "answer": "An error occurred while generating the answer.",
                "confidence": "low",
                "citations": [],
                "grounding_notes": f"Error: {e}"
            }

# --- Generator Factory ---

class Generator:
    """
    Factory class to provide the correct generator instance based on settings.
    """
    def __init__(self):
        self._generator_instance: Optional[BaseGenerator] = None
        self._initialize_generator()

    def _initialize_generator(self):
        """Initializes the appropriate generator based on LLM_PROVIDER setting."""
        provider = settings.LLM_PROVIDER.lower()
        if provider == "openai":
            self._generator_instance = OpenAIGenerator()
        elif provider == "gemini":
            self._generator_instance = GeminiGenerator()
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER for generation: {settings.LLM_PROVIDER}")
        logger.info(f"Active Generator: {provider}")

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[Tuple[float, DocumentChunk]],
        job_id: str
    ) -> Dict[str, Any]:
        if not self._generator_instance:
            self._initialize_generator() # Try to re-initialize if it somehow became None
        return self._generator_instance.generate_answer(question, retrieved_chunks, job_id)