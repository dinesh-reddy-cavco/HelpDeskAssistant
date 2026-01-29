"""
Build the RAG prompt: system + user with retrieved context.
Enforces: answer ONLY from context; if not found, say so.
"""
from __future__ import annotations

import logging
from typing import List

from app.models import SourceDocument
from app.services.rag.prompts import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE

logger = logging.getLogger(__name__)

# Max context length (chars) to avoid token overflow; tune per model
MAX_CONTEXT_CHARS = 8000


def build_context_block(documents: List[SourceDocument]) -> str:
    """
    Format retrieved chunks into a single context string for the prompt.
    Each chunk is labeled with source/title so the model can cite if needed.
    """
    if not documents:
        return "(No relevant documents found in the knowledge base.)"
    parts = []
    for i, doc in enumerate(documents, 1):
        title = doc.title or doc.source_id
        section = f"[{doc.section_title}]" if doc.section_title else ""
        header = f"--- Document {i}: {title} {section} ---".strip()
        parts.append(f"{header}\n{doc.chunk_text}")
    return "\n\n".join(parts)


def build_rag_prompt(user_query: str, documents: List[SourceDocument]) -> tuple[str, str]:
    """
    Build system and user messages for RAG answer generation.
    Returns (system_prompt, user_message). Context is truncated if too long.
    """
    context = build_context_block(documents)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated.]"
        logger.debug("RAG context truncated to %d chars", MAX_CONTEXT_CHARS)
    user_message = RAG_USER_TEMPLATE.format(context=context, user_query=user_query.strip())
    return RAG_SYSTEM_PROMPT, user_message
