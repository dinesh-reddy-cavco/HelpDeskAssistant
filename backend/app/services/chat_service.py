"""Chat service for handling conversation logic."""
from app.services.openai_service import AzureOpenAIService
from app.services.logging_service import LoggingService
from app.models import ChatMessage, ChatResponse
from typing import List, Dict, Optional
import uuid
import logging

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chat conversations."""
    
    def __init__(self):
        """Initialize chat service with OpenAI service."""
        self.openai_service = AzureOpenAIService()
        self.logging_service = LoggingService()
    
    async def process_message(
        self,
        message: str,
        username: str,
        conversation_id: Optional[str] = None,
        history: Optional[List[ChatMessage]] = None
    ) -> ChatResponse:
        """
        Process a user message and generate a response.
        
        Args:
            message: User's message
            username: Username of the user
            conversation_id: Optional conversation ID for continuity
            history: Optional conversation history
            
        Returns:
            ChatResponse with assistant's reply
        """
        try:
            # Generate or use existing conversation ID
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # Prepare conversation history
            messages = []
            if history:
                for msg in history:
                    messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": message
            })
            
            # Get response from Azure OpenAI
            response_text = self.openai_service.get_chat_completion(messages)
            
            # Determine confidence and source (Phase 1: always generic)
            confidence = "high"  # In Phase 1, we'll be conservative
            source = "generic"
            requires_escalation = False
            
            # Simple heuristic: if response suggests escalation, mark it
            escalation_keywords = [
                "create a ticket",
                "contact support",
                "escalate",
                "unable to help",
                "not sure"
            ]
            if any(keyword in response_text.lower() for keyword in escalation_keywords):
                requires_escalation = True
            
            # Structured logging
            logger.info(
                "Message processed successfully",
                extra={
                    "username": username,
                    "conversation_id": conversation_id,
                    "confidence": confidence,
                    "source": source,
                    "requires_escalation": requires_escalation
                }
            )
            
            # Log conversation to database (fire and forget)
            conversation_record_id = 0
            try:
                conversation_record_id = await self.logging_service.log_conversation(
                    conversation_id=conversation_id,
                    username=username,
                    user_message=message,
                    assistant_response=response_text,
                    confidence=confidence,
                    source=source,
                    requires_escalation=requires_escalation
                )
            except Exception as log_error:
                logger.warning(f"Failed to log conversation: {str(log_error)}")
            
            return ChatResponse(
                response=response_text,
                conversation_id=conversation_id,
                confidence=confidence,
                source=source,
                requires_escalation=requires_escalation,
                conversation_record_id=conversation_record_id
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            raise Exception(f"Failed to process message: {str(e)}")
