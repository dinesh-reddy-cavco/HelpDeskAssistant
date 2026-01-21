"""Service for logging conversations to database."""
from app.database.db import AsyncSessionLocal
from app.database.models import Conversation
from typing import Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LoggingService:
    """Service for logging conversations."""
    
    async def log_conversation(
        self,
        conversation_id: str,
        username: str,
        user_message: str,
        assistant_response: str,
        confidence: Optional[str] = None,
        source: Optional[str] = None,
        requires_escalation: bool = False
    ):
        """
        Log a conversation to the database.
        
        Args:
            conversation_id: Unique conversation identifier
            username: Username of the user
            user_message: User's message
            assistant_response: Assistant's response
            confidence: Confidence level of the response
            source: Source of the answer (generic, rag, etc.)
            requires_escalation: Whether escalation is required
        """
        try:
            async with AsyncSessionLocal() as session:
                conversation = Conversation(
                    conversation_id=conversation_id,
                    username=username,
                    user_message=user_message,
                    assistant_response=assistant_response,
                    confidence=confidence,
                    source=source,
                    requires_escalation=requires_escalation,
                    timestamp=datetime.utcnow()
                )
                session.add(conversation)
                await session.commit()
                logger.info(
                    "Conversation logged to database",
                    extra={
                        "username": username,
                        "conversation_id": conversation_id,
                        "confidence": confidence,
                        "source": source,
                        "requires_escalation": requires_escalation
                    }
                )
        except Exception as e:
            logger.error(f"Error logging conversation: {str(e)}")
            # Don't raise - logging failures shouldn't break the chat
