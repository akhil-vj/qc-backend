"""
Coupon and discount models
"""

from sqlalchemy import Column, String, Integer, Numeric, Boolean, ForeignKey, Index, CheckConstraint, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
import uuid

from .base import Base, TimestampedModel

class Coupon(Base, TimestampedModel):
    """Discount coupons and promo codes"""
    
    __tablename__ = "coupons"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Discount details
    discount_type = Column(String(20), nullable=False)  # percentage, fixed
    discount_value = Column(Numeric(10, 2), nullable=False)
    
    # Conditions
    min_order_value = Column(Numeric(10, 2), nullable=True)
    max_discount = Column(Numeric(10, 2), nullable=True)
    
    # Usage limits
    usage_limit = Column(Integer, nullable=True)  # Total usage limit
    usage_limit_per_user = Column(Integer, default=1)
    used_count = Column(Integer, default=0)
    
    # Validity
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    
    # Applicability
    applicable_products = Column(ARRAY(UUID(as_uuid=True)), default=[])
    applicable_categories = Column(ARRAY(UUID(as_uuid=True)), default=[])
    applicable_sellers = Column(ARRAY(UUID(as_uuid=True)), default=[])
    
    # User restrictions
    user_type = Column(String(50), nullable=True)  # new, existing, premium
    minimum_tier = Column(String(50), nullable=True)  # bronze, silver, gold, platinum
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    usages = relationship("CouponUsage", back_populates="coupon")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("discount_value > 0", name="check_positive_discount"),
        CheckConstraint("usage_limit IS NULL OR usage_limit > 0", name="check_positive_usage_limit"),
        Index("idx_coupons_active_valid", "is_active", "valid_from", "valid_until"),
    )
    
    @property
    def is_valid(self):
        """Check if coupon is currently valid"""
        from datetime import datetime
        now = datetime.utcnow()
        
        if not self.is_active:
            return False
            
        if self.valid_from and now < self.valid_from:
            return False
            
        if self.valid_until and now > self.valid_until:
            return False
            
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False
            
        return True

class CouponUsage(Base, TimestampedModel):
    """Track coupon usage by users"""
    
    __tablename__ = "coupon_usages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coupon_id = Column(UUID(as_uuid=True), ForeignKey("coupons.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    
    # Discount applied
    discount_amount = Column(Numeric(10, 2), nullable=False)
    
    # Relationships
    coupon = relationship("Coupon", back_populates="usages")
    user = relationship("User")
    order = relationship("Order")
    
    # Indexes
    __table_args__ = (
        Index("idx_coupon_usages_coupon_user", "coupon_id", "user_id"),
        Index("idx_coupon_usages_order", "order_id"),
    )
