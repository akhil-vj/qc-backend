"""Admin audit log model"""

from sqlalchemy import Column, String, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base, TimestampedModel

class AdminLog(Base, TimestampedModel):
    """Log all admin actions for audit trail"""
    
    __tablename__ = "admin_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)  # ban_user, approve_product, etc.
    entity_type = Column(String(50), nullable=False)  # user, product, order, etc.
    entity_id = Column(String(200), nullable=False)
    description = Column(Text)
    old_values = Column(JSON)  # Store previous state
    new_values = Column(JSON)  # Store new state
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # Relationships
    admin = relationship("User", back_populates="admin_logs")
