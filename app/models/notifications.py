"""Notification related models"""

from sqlalchemy import Column, String, Boolean, ForeignKey, JSON, Text, DateTime, func, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid

from .base import Base, TimestampedModel

class NotificationLog(Base, TimestampedModel):
    """Log all sent notifications"""
    
    __tablename__ = "notification_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(50), nullable=False)  # sent, failed, broadcast
    message_id = Column(String(200))
    topic = Column(String(100))
    push_metadata = Column(JSON, default={})
    sent_at = Column(DateTime, default=func.now())
