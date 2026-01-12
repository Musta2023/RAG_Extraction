import logging
import re
import os
from typing import List, Tuple, Dict, Any, Optional
from abc import ABC, abstractmethod

# Third-party imports
try:
    import google.generativeai as genai
    import google.generativeai.types as types
except ImportError:
    genai = None
    types = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# Internal project imports
from app.config import settings
from app.models.document import DocumentChunk

logger = logging.getLogger(__name__)

class BaseGenerator(ABC):
    """
    Abstract base class for all answer generation implementations.
    """
    def __init__(self):
        pass

    def _format_context(self, retrieved_chunks: List[Tuple[float, DocumentChunk]]) -> Tuple[str, Dict[int, str]]:
        """
        Formats the retrieved chunks into a string that can be used as context
        for the LLM, and creates a mapping from source number to URL for citation.
        """
        formatted_context = ""
        source_map: Dict[int, str] = {}
        for i, (score, chunk) in enumerate(retrieved_chunks):
            source_num = i + 1
            formatted_context += f"[Source {source_num}] {chunk.text_content}\n\n"
            source_map[source_num] = str(chunk.document_url)
        return formatted_context.strip(), source_map


    @abstractmethod
    async def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[Tuple[float, DocumentChunk]],
        job_id: str
    ) -> Dict[str, Any]:
        """
        Generates an answer based on the question and retrieved chunks.
        """
        pass

# --- OpenAI Generator Implementation ---

class OpenAIGenerator(BaseGenerator):
    """
    Answer generator using OpenAI's chat models.
    """
    def __init__(self):
        super().__init__()
        if OpenAI is None:
            raise ImportError("Please install 'openai' package.")
        
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_GENERATION_MODEL
        logger.info(f"Initialized OpenAIGenerator with model: {self.model}")

    async def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[Tuple[float, DocumentChunk]],
        job_id: str
    ) -> Dict[str, Any]:
        if not retrieved_chunks:
            return {
                "answer": "I don't know based on the provided documents.",
                "confidence": "low",
                "citations": [],
                "grounding_notes": "No relevant documents were retrieved."
            }

        context, source_map = self._format_context(retrieved_chunks)
        
        system_prompt = (
            "You are a helpful and honest assistant. Answer STRICTLY based on the provided sources. "
            "For each factual claim, cite the source number (e.g., [Source 1]). "
            "If the answer is not in the sources, say 'I don't know based on the provided documents.' "
            "Do not hallucinate."
        )

        user_prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"

        try:
            # Note: OpenAI's SDK is technically synchronous here, but wrapped in async method
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0
            )
            answer_text = response.choices[0].message.content.strip()
            citations = self._generate_citations(answer_text, source_map)
            
            return {
                "answer": answer_text,
                "confidence": self._assess_confidence(citations),
                "citations": citations,
                "grounding_notes": "Generated using OpenAI."
            }
        except Exception as e:
            logger.error(f"OpenAI Error: {e}")
            return {"answer": "Error generating answer.", "confidence": "low", "citations": [], "grounding_notes": str(e)}

# --- Google Gemini Generator Implementation ---

class GeminiGenerator(BaseGenerator):
    """
    Answer generator using Google's Gemini models via google-generativeai.
    """
    def __init__(self):
        super().__init__()
        if genai is None:
            raise ImportError("Please install 'google-generativeai' package.")
        
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_GENERATION_MODEL

        if not self.api_key or self.api_key == "your_gemini_api_key":
            logger.error("Gemini API key is not set.")
            self.model_name = None
        else:
            # IMPORTANT: Global configuration for google-generativeai
            genai.configure(api_key=self.api_key)
            logger.info(f"Initialized GeminiGenerator with model: {self.model_name}")

    async def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[Tuple[float, DocumentChunk]],
        job_id: str
    ) -> Dict[str, Any]:
        if not self.model_name:
            return {"answer": "Gemini API key not configured.", "confidence": "low", "citations": [], "grounding_notes": "Missing key."}

        if not retrieved_chunks:
            return {"answer": "I don't know based on the provided documents.", "confidence": "low", "citations": [], "grounding_notes": "No docs."}
        
        context, source_map = self._format_context(retrieved_chunks)

        system_instructions = (
            "You are a strict Retrieval-Augmented Generation (RAG) assistant.\n"
            "Use ONLY the provided Context.\n"
            "Do NOT use prior knowledge.\n"
            "If the answer is not explicitly present in the Context, respond exactly with:\n"
            "\"I cannot answer this question based on the provided information.\"\n"
            "Do NOT mention sources or citations.\n"
            "Do NOT add explanations."
        )

        user_prompt_template = (
            "Context:\n"
            "{context}\n\n"
            "Question:\n"
            "{question}\n\n"
            "Answer using ONLY the Context above."
        )
        user_prompt = user_prompt_template.format(context=context, question=question)

        try:
            model = genai.GenerativeModel(self.model_name)
            
            response = await model.generate_content_async(
                contents=[
                    {"role": "user", "parts": [{"text": system_instructions}]},
                    {"role": "model", "parts": [{"text": "Ok."}]},
                    {"role": "user", "parts": [{"text": user_prompt}]},
                ],
                generation_config={"temperature": 0.0},
                safety_settings=[]
            )
            answer_text = response.text.strip()
            
            citations = []
            confidence = "low" # Default to low
            grounding_notes = "Answer generated strictly from retrieved context."

            if answer_text == "I cannot answer this question based on the provided information.":
                confidence = "low"
                grounding_notes = "Abstained from answering due to insufficient context."
            else:
                # Programmatically attach citations: If an answer is given, we assume it comes from the retrieved chunks.
                # Therefore, all retrieved chunks are considered sources.
                unique_citations_with_snippets = {}
                for score, chunk in retrieved_chunks:
                    url = str(chunk.document_url)
                    snippet_sentences = re.split(r'(?<=[.!?])\s+', chunk.text_content)
                    snippet = " ".join(snippet_sentences[:3])
                    if len(snippet_sentences) > 3:
                        snippet += "..."
                    
                    if url not in unique_citations_with_snippets:
                        unique_citations_with_snippets[url] = {"url": url, "snippets": [snippet]}
                    else:
                        if snippet not in unique_citations_with_snippets[url]["snippets"]:
                            unique_citations_with_snippets[url]["snippets"].append(snippet)
                
                final_citations = []
                for citation_entry in unique_citations_with_snippets.values():
                    final_citations.append({
                        "url": citation_entry["url"],
                        "quote": " ".join(citation_entry["snippets"])
                    })
                
                citations = final_citations
                
                if citations:
                    confidence = "high"
                else:
                    # This case should ideally not happen if retrieved_chunks was not empty and an answer was given
                    confidence = "low"
                    grounding_notes += " Warning: No citations could be attached despite an answer being generated."
            
            return {
                "answer": answer_text,
                "confidence": confidence,
                "citations": citations,
                "grounding_notes": grounding_notes
            }
        except Exception as e:
            logger.exception(f"Gemini Error for job {job_id}: ")
            return {"answer": "An error occurred with Gemini.", "confidence": "low", "citations": [], "grounding_notes": str(e)}

# --- Generator Factory ---

class Generator:
    """
    Factory class to provide the correct generator instance.
    """
    def __init__(self):
        self._generator_instance: Optional[BaseGenerator] = None
        self._initialize_generator()

    def _initialize_generator(self):
        provider = settings.LLM_PROVIDER.lower()
        if provider == "openai":
            self._generator_instance = OpenAIGenerator()
        elif provider == "gemini":
            self._generator_instance = GeminiGenerator()
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")
        logger.info(f"Active Generator Provider: {provider}")

    async def generate_answer(
        self,
        question: str,
        retrieved_chunks: List[Tuple[float, DocumentChunk]],
        job_id: str
    ) -> Dict[str, Any]:
        if not self._generator_instance:
            self._initialize_generator()
        return await self._generator_instance.generate_answer(question, retrieved_chunks, job_id)

