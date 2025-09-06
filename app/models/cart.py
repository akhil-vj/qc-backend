"""
Shopping cart model
Handles both authenticated and session-based carts
"""

from sqlalchemy import Column, String, Integer, Numeric, Boolean, ForeignKey, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from .base import Base, TimestampedModel

class CartItem(Base, TimestampedModel):
    """Shopping cart items"""
    
    __tablename__ = "cart_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User or session
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    session_id = Column(String(255), nullable=True)
    
    # Product
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    
    # Quantity and price
    quantity = Column(Integer, nullable=False, default=1)
    price = Column(Numeric(10, 2), nullable=False)  # Price at time of adding
    
    # Status
    saved_for_later = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="cart_items")
    product = relationship("Product", back_populates="cart_items")
    variant = relationship("ProductVariant")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", "variant_id", name="uq_user_product_variant"),
        UniqueConstraint("session_id", "product_id", "variant_id", name="uq_session_product_variant"),
        CheckConstraint("quantity > 0", name="check_positive_cart_quantity"),
        CheckConstraint("(user_id IS NOT NULL) OR (session_id IS NOT NULL)", name="check_user_or_session"),
        Index("idx_cart_items_user_saved", "user_id", "saved_for_later"),
        Index("idx_cart_items_session", "session_id"),
    )
