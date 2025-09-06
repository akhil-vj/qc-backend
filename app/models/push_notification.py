"""Push notification models"""

from sqlalchemy import Column, String, Boolean, ForeignKey, JSON, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base, TimestampedModel

class DeviceToken(Base, TimestampedModel):
    """Store FCM device tokens for users"""
    
    __tablename__ = "device_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(500), unique=True, nullable=False, index=True)
    device_type = Column(String(50), nullable=False)  # ios, android, web
    device_name = Column(String(200))
    device_model = Column(String(200))
    app_version = Column(String(50))
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="device_tokens")

class PushNotificationLog(Base, TimestampedModel):
    """Log all sent push notifications"""
    
    __tablename__ = "push_notification_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    data = Column(JSON)
    image_url = Column(String(500))
    action_url = Column(String(500))
    notification_type = Column(String(100))  # order_update, flash_sale, promotion, etc.
    status = Column(String(50), default="pending")  # pending, sent, failed
    error_message = Column(Text)
    sent_at = Column(DateTime(timezone=True))
    opened_at = Column(DateTime(timezone=True))
    fcm_message_id = Column(String(200))
