"""Price history model with versioning"""

from sqlalchemy import Column, Numeric, String, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base, TimestampedModel, UUIDModel, VersionedModel

class PriceHistory(Base, TimestampedModel, UUIDModel, VersionedModel):
    """Price history tracking with versioning"""
    
    __tablename__ = "price_history"
    
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    old_price = Column(Numeric(10, 2), nullable=False)
    new_price = Column(Numeric(10, 2), nullable=False)
    old_mrp = Column(Numeric(10, 2))  # keeping for compatibility
    new_mrp = Column(Numeric(10, 2))  # keeping for compatibility
    change_percentage = Column(Numeric(5, 2))
    change_reason = Column(String(200))
    reason = Column(String(255))  # keeping for compatibility
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    product = relationship("Product", back_populates="price_history")
    
    # Indexes
    __table_args__ = (
        Index("idx_price_history_product_created", "product_id", "created_at"),
    )
    
    def calculate_change_percentage(self):
        """Calculate price change percentage"""
        if self.old_price > 0:
            self.change_percentage = ((self.new_price - self.old_price) / self.old_price) * 100
        else:
            self.change_percentage = 0
