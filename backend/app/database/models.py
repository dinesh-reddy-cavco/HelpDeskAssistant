"""Database models for conversation logging."""
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Conversation(Base):
    """Model for storing conversation logs with feedback."""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, index=True, nullable=False)
    username = Column(String, index=True, nullable=False)
    user_message = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)
    confidence = Column(String, nullable=True)
    source = Column(String, nullable=True)
    requires_escalation = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Feedback fields for training data collection
    feedback_rating = Column(String, nullable=True)  # "thumbs_up" or "thumbs_down"
    feedback_reason_code = Column(String, nullable=True)  # Reason code for thumbs down
    feedback_timestamp = Column(DateTime, nullable=True)  # When feedback was provided
    feedback_notes = Column(Text, nullable=True)  # Optional additional notes
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, conversation_id={self.conversation_id}, username={self.username}, feedback={self.feedback_rating})>"
