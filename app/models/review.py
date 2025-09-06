"""
Product review and rating model
"""

from sqlalchemy import Column, String, Integer, Text, Boolean, ForeignKey, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from .base import Base, TimestampedModel

class Review(Base, TimestampedModel):
    """Product reviews and ratings"""
    
    __tablename__ = "reviews"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    
    # Review content
    rating = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)
    
    # Media
    images = Column(JSONB, default=[])
    
    # Verification
    is_verified_purchase = Column(Boolean, default=False)
    
    # Engagement
    helpful_count = Column(Integer, default=0)
    unhelpful_count = Column(Integer, default=0)
    
    # Status
    is_approved = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    
    # Relationships
    product = relationship("Product", back_populates="reviews")
    user = relationship("User", back_populates="reviews")
    order = relationship("Order", back_populates="reviews")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("product_id", "user_id", "order_id", name="uq_product_user_order_review"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_rating_range"),
        Index("idx_reviews_product_approved", "product_id", "is_approved"),
        Index("idx_reviews_user", "user_id"),
    )
