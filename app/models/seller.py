"""
Seller profile and related models
"""

from sqlalchemy import Column, String, Boolean, Numeric, Integer, ForeignKey, Index, CheckConstraint, DateTime, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from .base import Base, TimestampedModel

class SellerProfile(Base, TimestampedModel):
    """Extended seller information"""
    
    __tablename__ = "seller_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    
    # Business information
    business_name = Column(String(255), nullable=True)
    business_type = Column(String(100), nullable=True)  # individual, company
    
    # Tax information
    gst_number = Column(String(50), nullable=True)
    pan_number = Column(String(20), nullable=True)
    
    # Address
    business_address = Column(JSONB, nullable=True)
    pickup_address = Column(JSONB, nullable=True)
    
    # Banking
    bank_details = Column(JSONB, nullable=True)  # Encrypted
    
    # Commission and payouts
    commission_rate = Column(Numeric(5, 2), default=5.00)
    payout_schedule = Column(String(50), default="weekly")  # daily, weekly, monthly
    minimum_payout = Column(Numeric(10, 2), default=100.00)
    
    # Verification
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_documents = Column(JSONB, default=[])
    
    # Performance metrics
    rating = Column(Numeric(3, 2), default=0.00)
    total_products = Column(Integer, default=0)
    total_orders = Column(Integer, default=0)
    total_sales = Column(Numeric(12, 2), default=0.00)
    
    # Policies
    return_policy = Column(JSONB, default={})
    shipping_policy = Column(JSONB, default={})
    
    # Status
    is_active = Column(Boolean, default=True)
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    suspension_reason = Column(String(500), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="seller_profile")
    payouts = relationship("SellerPayout", back_populates="seller_profile")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("commission_rate >= 0 AND commission_rate <= 100", name="check_commission_rate"),
        CheckConstraint("rating >= 0 AND rating <= 5", name="check_seller_rating"),
        Index("idx_seller_profiles_verified_active", "is_verified", "is_active"),
    )

class SellerPayout(Base, TimestampedModel):
    """Seller payout records"""
    
    __tablename__ = "seller_payouts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_profile_id = Column(UUID(as_uuid=True), ForeignKey("seller_profiles.id"), nullable=False)
    
    # Payout details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="INR")
    
    # Period
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    
    # Transaction details
    transaction_id = Column(String(255), nullable=True)
    transaction_date = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    failure_reason = Column(String(500), nullable=True)
    
    # Order summary
    orders_count = Column(Integer, default=0)
    orders_total = Column(Numeric(12, 2), default=0.00)
    commission_amount = Column(Numeric(10, 2), default=0.00)
    
    # Relationships
    seller_profile = relationship("SellerProfile", back_populates="payouts")
    
    # Indexes
    __table_args__ = (
        Index("idx_seller_payouts_seller_status", "seller_profile_id", "status"),
        Index("idx_seller_payouts_period", "period_start", "period_end"),
    )
