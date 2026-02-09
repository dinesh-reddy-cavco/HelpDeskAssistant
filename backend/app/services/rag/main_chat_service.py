"""
Main chat service: orchestrates intent → generic or RAG path.
- Generic: never hit vector DB; answer with Foundry only.
- CAVCO_SPECIFIC: retrieve → RAG prompt → generate → confidence gate.
- Confidence < threshold → ESCALATION_REQUIRED (no hallucination).
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from app.config import settings
from app.models import ChatMessage, ChatResponse, SourceDocument
from app.services.logging_service import LoggingService
from app.services.openai_service import AzureOpenAIService
from app.services.rag.intent_classifier import IntentClassifier
from app.services.rag.retriever import retrieve as retrieve_docs
from app.services.rag.answer_generator import AnswerGenerator
from app.services.rag.confidence_scorer import score_confidence

logger = logging.getLogger(__name__)


def _run_rag_path(
    message: str,
    answer_gen: AnswerGenerator,
    openai_svc: AzureOpenAIService,
    username: str,
    conversation_id: str,
) -> tuple[str, float, str, bool, List[SourceDocument], List[str]]:
    """
    Run RAG: retrieve → generate → score → gate.
    Returns (response_text, confidence_score, answer_type, requires_escalation, sources, document_ids).
    """
    retrieval_used = True
    docs = retrieve_docs(message, top_k=settings.rag_top_k)
    document_ids = [d.source_id for d in docs]
    page_titles = [d.title or d.source_id for d in docs]
    logger.info(
        "Retrieval returned %d documents",
        len(docs),
        extra={
            "username": username,
            "user_id": username,
            "conversation_id": conversation_id,
            "num_docs": len(docs),
            "document_ids": document_ids[:20],
            "page_titles": page_titles[:20],
            "user_query": message[:200],
        },
    )
    if not docs:
        return (
            "I couldn't find relevant information in the knowledge base. This issue may require creating a support ticket.",
            0.0,
            "ESCALATION_REQUIRED",
            True,
            [],
            document_ids,
        )
    response_text = answer_gen.generate(message, docs)
    confidence_score = score_confidence(
        message, response_text, sources_count=len(docs), use_llm=True, openai_service=openai_svc
    )
    threshold = settings.confidence_threshold
    escalation_gated = confidence_score < threshold
    logger.info(
        "Confidence: score=%.2f, threshold=%.2f, escalation_gated=%s",
        confidence_score,
        threshold,
        escalation_gated,
        extra={
            "username": username,
            "user_id": username,
            "conversation_id": conversation_id,
            "confidence_score": confidence_score,
            "confidence_threshold": threshold,
            "escalation_gated": escalation_gated,
        },
    )
    if escalation_gated:
        response_text = settings.escalation_message
        answer_type = "ESCALATION_REQUIRED"
        requires_escalation = True
    else:
        answer_type = "RAG"
        requires_escalation = False
    return response_text, confidence_score, answer_type, requires_escalation, docs, document_ids


class MainChatService:
    """
    Enterprise RAG chat: intent classification, then either generic LLM or RAG.
    Do not mix generic and RAG answers. Generic questions never hit the vector DB.
    """

    def __init__(
        self,
        openai_service: Optional[AzureOpenAIService] = None,
        logging_service: Optional[LoggingService] = None,
    ):
        self._openai = openai_service or AzureOpenAIService()
        self._logging = logging_service or LoggingService()
        self._intent = IntentClassifier(self._openai)
        self._answer_gen = AnswerGenerator(self._openai)

    async def process_message(
        self,
        message: str,
        username: str,
        conversation_id: Optional[str] = None,
        history: Optional[List[ChatMessage]] = None,
    ) -> ChatResponse:
        """
        Full flow: classify intent → GENERIC (Foundry only) or CAVCO_SPECIFIC (retrieve + RAG).
        Apply confidence gating; return answer_type and sources when RAG.
        """
        cid = conversation_id or str(uuid.uuid4())
        retrieval_used = False
        document_ids: List[str] = []
        confidence_score: Optional[float] = None
        answer_type: str = "GENERIC"
        sources: Optional[List[SourceDocument]] = None
        response_text: str
        requires_escalation = False
        conversation_record_id = 0

        # 1. Intent classification (LLM-based)
        intent = self._intent.classify(message)
        logger.info(
            "Intent classified",
            extra={
                "username": username,
                "user_id": username,
                "conversation_id": cid,
                "user_query": message[:200],
                "intent": intent,
            },
        )

        if intent == "GENERIC":
            # 2a. Generic path: Foundry only, no vector DB
            response_text = self._generic_answer(message, history)
            confidence_score = 0.9
            answer_type = "GENERIC"
            confidence_str = "high"
            source_str = "generic"
        elif intent == "OFF_TOPIC":
            # 2b. Off-topic (weather, sports, etc.): decline politely, no RAG, no generic answer
            response_text = settings.off_topic_message
            confidence_score = 0.0
            answer_type = "OFF_TOPIC"
            requires_escalation = False
            sources = []
            confidence_str = "low"
            source_str = "off_topic"
            logger.info(
                "Intent OFF_TOPIC: declining non-IT question",
                extra={
                    "username": username,
                    "user_id": username,
                    "conversation_id": cid,
                    "user_query": message[:200],
                    "intent": intent,
                },
            )
        elif intent == "UNKNOWN":
            # 2c. UNKNOWN: escalate (RAG only runs for CAVCO_SPECIFIC)
            response_text = settings.escalation_message
            confidence_score = 0.0
            answer_type = "ESCALATION_REQUIRED"
            requires_escalation = True
            sources = []
            confidence_str = "low"
            source_str = "unknown"
            logger.info(
                "Intent UNKNOWN: escalating (RAG only runs for CAVCO_SPECIFIC)",
                extra={
                    "username": username,
                    "user_id": username,
                    "conversation_id": cid,
                    "user_query": message[:200],
                    "intent": intent,
                },
            )
        else:
            # 2d. CAVCO_SPECIFIC: RAG path (retrieve → generate → score → gate)
            if not settings.azure_search_endpoint or not settings.azure_search_key:
                response_text = settings.escalation_message
                confidence_score = 0.0
                answer_type = "ESCALATION_REQUIRED"
                requires_escalation = True
                sources = []
                confidence_str = "low"
                source_str = "rag"
                logger.warning("Azure AI Search not configured; returning escalation for non-GENERIC intent")
            else:
                retrieval_used = True
                logger.info(
                    "RAG path: retrieving top_k=%s",
                    settings.rag_top_k,
                    extra={
                        "username": username,
                        "user_id": username,
                        "conversation_id": cid,
                        "intent": intent,
                        "top_k": settings.rag_top_k,
                    },
                )
                (
                    response_text,
                    confidence_score,
                    answer_type,
                    requires_escalation,
                    sources,
                    document_ids,
                ) = _run_rag_path(
                    message,
                    self._answer_gen,
                    self._openai,
                    username,
                    cid,
                )
                confidence_str = "high" if (confidence_score or 0) >= settings.confidence_threshold else "low"
                source_str = "rag"

        # 3. Log request: summary for console, full extras for file (intent, retrieval, docs, confidence, decision)
        num_docs = len(document_ids)
        score_str = f"{confidence_score:.2f}" if confidence_score is not None else "N/A"
        summary_msg = (
            f"Chat completed | intent={intent} retrieval={retrieval_used} docs={num_docs} "
            f"confidence={score_str} answer_type={answer_type}"
        )
        page_titles = [d.title or d.source_id for d in (sources or [])][:20]
        logger.info(
            summary_msg,
            extra={
                "username": username,
                "user_id": username,
                "conversation_id": cid,
                "user_query": message[:200],
                "intent": intent,
                "retrieval_used": retrieval_used,
                "document_ids": document_ids[:20],
                "page_titles": page_titles,
                "num_docs": num_docs,
                "confidence_score": confidence_score,
                "answer_type": answer_type,
                "final_decision": answer_type,
            },
        )
        try:
            conversation_record_id = await self._logging.log_conversation(
                conversation_id=cid,
                username=username,
                user_message=message,
                assistant_response=response_text,
                confidence=confidence_str,
                source=source_str,
                requires_escalation=requires_escalation,
            )
        except Exception as e:
            logger.warning("Failed to log conversation: %s", e)

        return ChatResponse(
            response=response_text,
            conversation_id=cid,
            confidence=confidence_str,
            confidence_score=confidence_score,
            source=source_str,
            answer_type=answer_type,
            sources=sources,
            requires_escalation=requires_escalation,
            conversation_record_id=conversation_record_id,
        )

    def _generic_answer(self, message: str, history: Optional[List[ChatMessage]] = None) -> str:
        """Answer using Foundry only (default system prompt). No RAG."""
        messages = []
        if history:
            for msg in history:
                messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": message})
        return self._openai.get_chat_completion(messages, temperature=0.7, max_tokens=500)
