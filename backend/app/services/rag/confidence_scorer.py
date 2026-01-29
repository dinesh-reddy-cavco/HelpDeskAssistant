"""
Confidence scoring for RAG answers: 0–1.
Used for gating: below threshold → ESCALATION_REQUIRED (no hallucination).
Implements LLM self-evaluation; heuristic fallback if needed.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.config import settings
from app.services.openai_service import AzureOpenAIService
from app.services.rag.prompts import CONFIDENCE_SCORING_SYSTEM, CONFIDENCE_SCORING_USER_TEMPLATE

logger = logging.getLogger(__name__)


def score_confidence_llm(
    user_query: str,
    answer_text: str,
    openai_service: AzureOpenAIService | None = None,
) -> float:
    """
    Score confidence (0–1) using LLM self-evaluation.
    Returns a value in [0, 1]; invalid response → 0.0.
    """
    if not answer_text or not answer_text.strip():
        return 0.0
    svc = openai_service or AzureOpenAIService()
    user_content = CONFIDENCE_SCORING_USER_TEMPLATE.format(
        user_query=user_query.strip(),
        answer_text=answer_text.strip(),
    )
    messages = [{"role": "user", "content": user_content}]
    response = svc.get_chat_completion(
        messages,
        temperature=0.0,
        max_tokens=10,
        system_prompt_override=CONFIDENCE_SCORING_SYSTEM,
    )
    # Parse number from response (e.g. "0.85" or "0.85.")
    match = re.search(r"0?\.\d+", (response or "").strip())
    if match:
        try:
            score = float(match.group(0))
            return max(0.0, min(1.0, score))
        except ValueError:
            pass
    logger.warning("Confidence scorer could not parse score from: %r", response)
    return 0.0


def score_confidence_heuristic(
    user_query: str,
    answer_text: str,
    has_sources: bool,
    num_sources: int = 0,
) -> float:
    """
    Heuristic fallback: combine answer length, presence of sources, and escalation phrases.
    Use when LLM scoring is disabled or fails.
    """
    score = 0.5
    if has_sources and num_sources > 0:
        score += 0.2 * min(num_sources, 5) / 5  # up to +0.2 for 5+ sources
    if len(answer_text.strip()) < 50:
        score -= 0.2  # very short answers often "I don't know"
    low_confidence_phrases = [
        "couldn't find",
        "don't have",
        "not in the knowledge base",
        "create a support ticket",
        "not find that",
    ]
    if any(p in answer_text.lower() for p in low_confidence_phrases):
        score -= 0.2
    return max(0.0, min(1.0, score))


def score_confidence(
    user_query: str,
    answer_text: str,
    sources_count: int = 0,
    use_llm: bool = True,
    openai_service: AzureOpenAIService | None = None,
) -> float:
    """
    Return confidence score 0–1. Prefers LLM; falls back to heuristic if use_llm=False or parse fails.
    """
    if use_llm:
        try:
            return score_confidence_llm(user_query, answer_text, openai_service)
        except Exception as e:
            logger.warning("LLM confidence scoring failed, using heuristic: %s", e)
    return score_confidence_heuristic(
        user_query, answer_text, has_sources=(sources_count > 0), num_sources=sources_count
    )
