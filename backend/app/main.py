"""FastAPI application main file."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.models import ChatRequest, ChatResponse, FeedbackRequest, FeedbackResponse, FEEDBACK_REASON_CODES
from app.services.chat_service import ChatService
from app.services.feedback_service import FeedbackService
from app.database.db import init_db
from app.config import settings
import logging
import json
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from contextlib import asynccontextmanager

# Create logs directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Configure structured logging
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
            "line": record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'username'):
            log_entry['username'] = record.username
        if hasattr(record, 'conversation_id'):
            log_entry['conversation_id'] = record.conversation_id
        if hasattr(record, 'user_message'):
            log_entry['user_message'] = record.user_message[:200]  # Truncate long messages
        if hasattr(record, 'assistant_response'):
            log_entry['assistant_response'] = record.assistant_response[:200]
        if hasattr(record, 'confidence'):
            log_entry['confidence'] = record.confidence
        if hasattr(record, 'source'):
            log_entry['source'] = record.source
        if hasattr(record, 'requires_escalation'):
            log_entry['requires_escalation'] = record.requires_escalation
        if hasattr(record, 'feedback_rating'):
            log_entry['feedback_rating'] = record.feedback_rating
        if hasattr(record, 'feedback_reason_code'):
            log_entry['feedback_reason_code'] = record.feedback_reason_code
        if hasattr(record, 'conversation_record_id'):
            log_entry['conversation_record_id'] = record.conversation_record_id
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, settings.log_level.upper()))

# Console handler with simple format
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
console_handler.setFormatter(console_formatter)

# File handler with structured JSON format
file_handler = RotatingFileHandler(
    log_dir / "app.log",
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(StructuredFormatter())

# Add handlers
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup: Initialize database
    await init_db()
    yield
    # Shutdown: Add cleanup code here if needed


# Initialize FastAPI app with lifespan handler
app = FastAPI(
    title="Cavco Help Desk Assistant API",
    description="AI-powered help desk chatbot API",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
chat_service = ChatService()
feedback_service = FeedbackService()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Cavco Help Desk Assistant API",
        "version": "1.0.0",
        "phase": "Phase 1: Foundation & Safe First Demo"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "help-desk-assistant"
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint for processing user messages.
    
    Args:
        request: ChatRequest with user message, username, and optional history
        
    Returns:
        ChatResponse with assistant's reply
    """
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        if not request.username or not request.username.strip():
            raise HTTPException(status_code=400, detail="Username is required")
        
        # Structured logging for conversation start
        logger.info(
            "Chat request received",
            extra={
                "username": request.username,
                "conversation_id": request.conversation_id or "new",
                "user_message": request.message,
                "message_length": len(request.message)
            }
        )
        
        # Convert history if provided
        history = None
        if request.history:
            history = request.history
        
        # Process message
        response = await chat_service.process_message(
            message=request.message,
            username=request.username,
            conversation_id=request.conversation_id,
            history=history
        )
        
        # Structured logging for conversation completion
        logger.info(
            "Chat response generated",
            extra={
                "username": request.username,
                "conversation_id": response.conversation_id,
                "confidence": response.confidence,
                "source": response.source,
                "requires_escalation": response.requires_escalation,
                "response_length": len(response.response)
            }
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error in chat endpoint",
            extra={
                "username": request.username if hasattr(request, 'username') else "unknown",
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/api/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """
    Submit feedback for a conversation.
    
    Args:
        request: FeedbackRequest with rating, reason_code (for thumbs_down), and optional notes
        
    Returns:
        FeedbackResponse indicating success or failure
    """
    try:
        # Validate thumbs_down requires reason_code
        if request.rating == "thumbs_down" and not request.reason_code:
            raise HTTPException(
                status_code=400,
                detail="reason_code is required when rating is 'thumbs_down'"
            )
        
        # Validate reason_code if provided
        if request.reason_code and request.reason_code not in FEEDBACK_REASON_CODES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid reason_code. Must be one of: {list(FEEDBACK_REASON_CODES.keys())}"
            )
        
        # Submit feedback
        success = await feedback_service.submit_feedback(
            conversation_record_id=request.conversation_record_id,
            rating=request.rating,
            reason_code=request.reason_code,
            notes=request.notes
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation record {request.conversation_record_id} not found"
            )
        
        logger.info(
            "Feedback submitted",
            extra={
                "conversation_record_id": request.conversation_record_id,
                "rating": request.rating,
                "reason_code": request.reason_code
            }
        )
        
        return FeedbackResponse(
            success=True,
            message="Feedback submitted successfully",
            conversation_record_id=request.conversation_record_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error in feedback endpoint",
            extra={
                "conversation_record_id": request.conversation_record_id if hasattr(request, 'conversation_record_id') else None,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/feedback/reason-codes")
async def get_feedback_reason_codes():
    """Get available feedback reason codes for thumbs down."""
    return {
        "reason_codes": FEEDBACK_REASON_CODES
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
