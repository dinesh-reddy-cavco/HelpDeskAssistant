"""Centralized application logging configuration."""

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "username"):
            log_entry["username"] = record.username
        if hasattr(record, "conversation_id"):
            log_entry["conversation_id"] = record.conversation_id
        if hasattr(record, "user_message"):
            log_entry["user_message"] = record.user_message[:200]  # Truncate long messages
        if hasattr(record, "user_query"):
            log_entry["user_query"] = (
                record.user_query[:200]
                if isinstance(record.user_query, str)
                else record.user_query
            )
        if hasattr(record, "assistant_response"):
            log_entry["assistant_response"] = record.assistant_response[:200]
        if hasattr(record, "confidence"):
            log_entry["confidence"] = record.confidence
        if hasattr(record, "source"):
            log_entry["source"] = record.source
        if hasattr(record, "requires_escalation"):
            log_entry["requires_escalation"] = record.requires_escalation
        if hasattr(record, "feedback_rating"):
            log_entry["feedback_rating"] = record.feedback_rating
        if hasattr(record, "feedback_reason_code"):
            log_entry["feedback_reason_code"] = record.feedback_reason_code
        if hasattr(record, "conversation_record_id"):
            log_entry["conversation_record_id"] = record.conversation_record_id
        # RAG-related extras (for debugging intent -> retrieval -> confidence -> decision)
        if hasattr(record, "intent"):
            log_entry["intent"] = record.intent
        if hasattr(record, "retrieval_used"):
            log_entry["retrieval_used"] = record.retrieval_used
        if hasattr(record, "document_ids"):
            log_entry["document_ids"] = record.document_ids
        if hasattr(record, "page_titles"):
            log_entry["page_titles"] = record.page_titles
        if hasattr(record, "num_docs"):
            log_entry["num_docs"] = record.num_docs
        if hasattr(record, "confidence_score"):
            log_entry["confidence_score"] = record.confidence_score
        if hasattr(record, "confidence_threshold"):
            log_entry["confidence_threshold"] = record.confidence_threshold
        if hasattr(record, "answer_type"):
            log_entry["answer_type"] = record.answer_type
        if hasattr(record, "final_decision"):
            log_entry["final_decision"] = record.final_decision
        if hasattr(record, "escalation_gated"):
            log_entry["escalation_gated"] = record.escalation_gated
        if hasattr(record, "top_k"):
            log_entry["top_k"] = record.top_k
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def configure_logging(log_level: str = "INFO") -> None:
    """Configure root logger and standard noise filters for the app."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    existing_handler_names = {handler.get_name() for handler in root_logger.handlers}

    if "app_console_handler" not in existing_handler_names:
        console_handler = logging.StreamHandler()
        console_handler.set_name("app_console_handler")
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        root_logger.addHandler(console_handler)

    if "app_file_handler" not in existing_handler_names:
        file_handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.set_name("app_file_handler")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(file_handler)

    # Reduce noise from HTTP clients: Azure SDK and httpx log every request/response at INFO
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)
