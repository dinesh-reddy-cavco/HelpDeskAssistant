"""Service for handling user feedback on conversations."""
from app.database.db import AsyncSessionLocal
from app.database.models import Conversation
from typing import Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service for managing user feedback."""
    
    async def submit_feedback(
        self,
        conversation_record_id: int,
        rating: str,
        reason_code: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        Submit feedback for a conversation.
        
        Args:
            conversation_record_id: ID of the conversation record
            rating: "thumbs_up" or "thumbs_down"
            reason_code: Reason code for thumbs down (required if rating is thumbs_down)
            notes: Optional additional notes
            
        Returns:
            True if feedback was successfully recorded
        """
        try:
            async with AsyncSessionLocal() as session:
                # Find the conversation record
                from sqlalchemy import select
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conversation_record_id)
                )
                conversation = result.scalar_one_or_none()
                
                if not conversation:
                    logger.warning(f"Conversation record {conversation_record_id} not found")
                    return False
                
                # Update feedback fields
                conversation.feedback_rating = rating
                conversation.feedback_reason_code = reason_code
                conversation.feedback_notes = notes
                conversation.feedback_timestamp = datetime.utcnow()
                
                await session.commit()
                
                logger.info(
                    "Feedback submitted",
                    extra={
                        "conversation_record_id": conversation_record_id,
                        "rating": rating,
                        "reason_code": reason_code,
                        "username": conversation.username
                    }
                )
                
                return True
                
        except Exception as e:
            logger.error(
                f"Error submitting feedback: {str(e)}",
                extra={"conversation_record_id": conversation_record_id},
                exc_info=True
            )
            return False
