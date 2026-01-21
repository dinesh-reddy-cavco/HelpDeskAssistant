"""Data models for API requests and responses."""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class ChatMessage(BaseModel):
    """Single chat message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str
    username: str
    conversation_id: Optional[str] = None
    history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str
    conversation_id: str
    confidence: Optional[str] = None
    source: Optional[str] = None  # "generic", "rag", "ticket_creation"
    requires_escalation: bool = False
    conversation_record_id: Optional[int] = None  # ID of the conversation record for feedback


# Feedback reason codes for thumbs down
FEEDBACK_REASON_CODES = {
    "incorrect_information": "Incorrect or inaccurate information",
    "not_helpful": "Response was not helpful",
    "incomplete_answer": "Answer was incomplete",
    "wrong_tone": "Wrong tone or style",
    "off_topic": "Response was off-topic",
    "technical_error": "Technical error in response",
    "other": "Other reason"
}


class FeedbackRequest(BaseModel):
    """Request model for feedback endpoint."""
    conversation_record_id: int = Field(..., description="ID of the conversation record to provide feedback on")
    rating: Literal["thumbs_up", "thumbs_down"] = Field(..., description="Feedback rating")
    reason_code: Optional[str] = Field(None, description="Reason code for thumbs down (required if rating is thumbs_down)")
    notes: Optional[str] = Field(None, description="Optional additional notes")


class FeedbackResponse(BaseModel):
    """Response model for feedback endpoint."""
    success: bool
    message: str
    conversation_record_id: int