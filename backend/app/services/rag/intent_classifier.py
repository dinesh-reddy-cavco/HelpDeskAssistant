"""
Intent classification using the LLM (not regex).
Outputs: GENERIC | CAVCO_SPECIFIC | OFF_TOPIC | UNKNOWN.
Generic questions must never hit the vector DB.
"""
from __future__ import annotations

import logging
from typing import Literal

from app.config import settings
from app.services.openai_service import AzureOpenAIService
from app.services.rag.prompts import INTENT_CLASSIFICATION_SYSTEM, INTENT_CLASSIFICATION_USER_TEMPLATE

logger = logging.getLogger(__name__)

IntentLabel = Literal["GENERIC", "CAVCO_SPECIFIC", "OFF_TOPIC", "UNKNOWN"]
VALID_LABELS: tuple[str, ...] = ("GENERIC", "CAVCO_SPECIFIC", "OFF_TOPIC", "UNKNOWN")


class IntentClassifier:
    """Classify user query as GENERIC, CAVCO_SPECIFIC, OFF_TOPIC, or UNKNOWN using the LLM."""

    def __init__(self, openai_service: AzureOpenAIService | None = None):
        self._openai = openai_service or AzureOpenAIService()

    def classify(self, user_query: str) -> IntentLabel:
        """
        Classify the user message. Returns one of GENERIC, CAVCO_SPECIFIC, OFF_TOPIC, UNKNOWN.
        We use a dedicated completion call (no chat history) so classification is stateless.
        """
        if not user_query or not user_query.strip():
            return "UNKNOWN"

        user_content = INTENT_CLASSIFICATION_USER_TEMPLATE.format(user_query=user_query.strip())
        messages = [{"role": "user", "content": user_content}]
        # Use low temperature and custom system prompt for consistent labels
        response_text = self._openai.get_chat_completion(
            messages,
            temperature=0.0,
            max_tokens=20,
            system_prompt_override=INTENT_CLASSIFICATION_SYSTEM,
        )
        label = (response_text or "").strip().upper()
        # Handle "GENERIC." or "CAVCO_SPECIFIC." etc.
        for valid in VALID_LABELS:
            if label.startswith(valid):
                return valid  # type: ignore[return-value]
        logger.warning("Intent classifier returned unexpected label: %r; defaulting to UNKNOWN", label)
        return "UNKNOWN"
