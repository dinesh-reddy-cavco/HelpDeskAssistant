"""Database models for conversation logging."""
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Conversation(Base):
    """Model for storing conversation logs."""
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
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, conversation_id={self.conversation_id}, username={self.username})>"
