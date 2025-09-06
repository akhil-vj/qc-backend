"""Referral system models"""

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base, TimestampedModel

class ReferralTracking(Base, TimestampedModel):
    """Track referrals between users"""
    
    __tablename__ = "referral_tracking"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referrer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    referred_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    referral_code = Column(String(50), nullable=False)
    status = Column(String(50), default="pending")  # pending, completed, cancelled
    completed_at = Column(DateTime(timezone=True))
    reward_coins = Column(Integer, default=0)
    
    # Relationships
    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="referral_tracking_made")
    referred_user = relationship("User", foreign_keys=[referred_user_id], back_populates="referral_tracking_received")
