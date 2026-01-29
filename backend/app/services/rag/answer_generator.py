"""
Generate RAG answer using retrieved context and LLM.
RAG answers must never rely on LLM prior knowledge — only provided context.
"""
from __future__ import annotations

import logging
from typing import List

from app.models import SourceDocument
from app.services.openai_service import AzureOpenAIService
from app.services.rag.rag_prompt_builder import build_rag_prompt

logger = logging.getLogger(__name__)


class AnswerGenerator:
    """Generate answer grounded strictly in retrieved context."""

    def __init__(self, openai_service: AzureOpenAIService | None = None):
        self._openai = openai_service or AzureOpenAIService()

    def generate(
        self,
        user_query: str,
        documents: List[SourceDocument],
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> str:
        """
        Generate answer using only the provided context. No prior knowledge.
        If context is empty or insufficient, the prompt instructs the model to say so.
        """
        if not documents:
            return (
                "I couldn't find relevant information in the knowledge base for this question. "
                "This issue may require creating a support ticket."
            )
        system_prompt, user_message = build_rag_prompt(user_query, documents)
        messages = [{"role": "user", "content": user_message}]
        # Low temperature for factual, grounded answers
        return self._openai.get_chat_completion(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt_override=system_prompt,
        )
