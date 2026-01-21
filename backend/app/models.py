"""Data models for API requests and responses."""
from pydantic import BaseModel
from typing import Optional, List
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
