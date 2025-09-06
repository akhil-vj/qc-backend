"""Coin transaction models"""

from sqlalchemy import Column, Integer, String, ForeignKey, Numeric, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base, TimestampedModel

class CoinTransaction(Base, TimestampedModel):
    """Track all coin transactions"""
    
    __tablename__ = "coin_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Integer, nullable=False)  # Positive for earned, negative for spent
    balance_after = Column(Integer, nullable=False)
    transaction_type = Column(String(50), nullable=False)  # earned, spent, expired
    source = Column(String(100), nullable=False)  # order, referral, daily_checkin, review, etc.
    reference_id = Column(String(200))  # Order ID, Review ID, etc.
    description = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    is_expired = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="coin_transactions")

class CoinRedemption(Base, TimestampedModel):
    """Track coin redemptions"""
    
    __tablename__ = "coin_redemptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    coins_redeemed = Column(Integer, nullable=False)
    redemption_type = Column(String(50), nullable=False)  # discount, coupon, product
    discount_amount = Column(Numeric(10, 2))
    coupon_code = Column(String(50))
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))
    status = Column(String(50), default="pending")  # pending, applied, cancelled
    
    # Relationships
    user = relationship("User", back_populates="coin_redemptions")
    order = relationship("Order", back_populates="coin_redemption")
