"""Centralized application logging configuration."""

import json
import logging
import threading
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from opencensus.ext.azure.log_exporter import AzureLogHandler
except ImportError:  # pragma: no cover - optional dependency at runtime
    AzureLogHandler = None


STRUCTURED_EXTRA_FIELDS = [
    "username",
    "user_id",
    "conversation_id",
    "conversation_record_id",
    "user_message",
    "user_query",
    "assistant_response",
    "confidence",
    "confidence_score",
    "confidence_threshold",
    "source",
    "requires_escalation",
    "feedback_rating",
    "feedback_reason_code",
    "intent",
    "retrieval_used",
    "document_ids",
    "page_titles",
    "num_docs",
    "answer_type",
    "final_decision",
    "escalation_gated",
    "top_k",
    "message_length",
    "response_length",
    "error",
]


def _ensure_handler_lock(handler: logging.Handler) -> None:
    """Ensure handler has a valid lock before it is used by logging internals."""
    if getattr(handler, "lock", None) is None:
        handler.createLock()
    # Python 3.14 expects a context-manager lock in Handler.handle().
    # Some third-party handlers (for example opencensus AzureLogHandler)
    # intentionally set lock=None in createLock(), so force a real lock.
    if getattr(handler, "lock", None) is None:
        handler.lock = threading.RLock()


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

        for field in STRUCTURED_EXTRA_FIELDS:
            if hasattr(record, field):
                value = getattr(record, field)
                if field in {"user_message", "user_query", "assistant_response"} and isinstance(value, str):
                    value = value[:200]
                log_entry[field] = value

        if "user_id" not in log_entry and "username" in log_entry:
            log_entry["user_id"] = log_entry["username"]
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class AppInsightsDimensionsFilter(logging.Filter):
    """Attach custom dimensions to records for Azure Application Insights queries."""

    def filter(self, record: logging.LogRecord) -> bool:
        dimensions: Dict[str, Any] = {}
        for field in STRUCTURED_EXTRA_FIELDS:
            if hasattr(record, field):
                dimensions[field] = getattr(record, field)

        if "user_id" not in dimensions and "username" in dimensions:
            dimensions["user_id"] = dimensions["username"]

        if dimensions:
            existing = getattr(record, "custom_dimensions", None)
            if isinstance(existing, dict):
                existing.update(dimensions)
                record.custom_dimensions = existing
            else:
                record.custom_dimensions = dimensions
        return True


def configure_logging(
    log_level: str = "INFO",
    app_insights_connection_string: Optional[str] = None,
) -> None:
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
        _ensure_handler_lock(console_handler)
        root_logger.addHandler(console_handler)

    if "app_file_handler" not in existing_handler_names:
        file_handler = TimedRotatingFileHandler(
            log_dir / "app.log",
            when="midnight",
            interval=1,
            backupCount=30,
            utc=True,
        )
        file_handler.suffix = "%Y-%m-%d"
        file_handler.set_name("app_file_handler")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(StructuredFormatter())
        _ensure_handler_lock(file_handler)
        root_logger.addHandler(file_handler)

    if (
        app_insights_connection_string
        and AzureLogHandler is not None
        and "app_insights_handler" not in existing_handler_names
    ):
        try:
            app_insights_handler = AzureLogHandler(
                connection_string=app_insights_connection_string
            )
            app_insights_handler.set_name("app_insights_handler")
            app_insights_handler.setLevel(getattr(logging, log_level.upper()))
            app_insights_handler.addFilter(AppInsightsDimensionsFilter())
            _ensure_handler_lock(app_insights_handler)
            root_logger.addHandler(app_insights_handler)
        except Exception as exc:
            root_logger.warning(
                "Failed to configure Azure Application Insights logging handler: %s",
                exc,
            )
    elif app_insights_connection_string and AzureLogHandler is None:
        root_logger.warning(
            "Application Insights connection string is configured, "
            "but 'opencensus-ext-azure' is not installed. "
            "Install it to enable Azure log export."
        )

    # Reduce noise from HTTP clients: Azure SDK and httpx log every request/response at INFO
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)
