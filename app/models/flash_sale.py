"""
Flash sale and time-limited deals models
"""

from sqlalchemy import Column, String, Integer, Numeric, Boolean, ForeignKey, Text, Index, CheckConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from .base import Base, TimestampedModel

class FlashSale(Base, TimestampedModel):
    """Flash sales and limited-time offers"""
    
    __tablename__ = "flash_sales"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    banner_image = Column(String(500), nullable=True)
    
    # Timing
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    
    # Limits
    max_quantity_per_user = Column(Integer, default=1)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    products = relationship("FlashSaleProduct", back_populates="flash_sale")
    
    # Indexes
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="check_valid_sale_period"),
        Index("idx_flash_sales_active_time", "is_active", "start_time", "end_time"),
    )
    
    @property
    def is_ongoing(self):
        """Check if flash sale is currently active"""
        from datetime import datetime
        now = datetime.utcnow()
        return self.is_active and self.start_time <= now <= self.end_time

class FlashSaleProduct(Base, TimestampedModel):
    """Products in flash sales"""
    
    __tablename__ = "flash_sale_products"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flash_sale_id = Column(UUID(as_uuid=True), ForeignKey("flash_sales.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    
    # Sale details
    sale_price = Column(Numeric(10, 2), nullable=False)
    discount_percentage = Column(Numeric(5, 2), nullable=False)
    
    # Inventory for sale
    sale_quantity = Column(Integer, nullable=False)
    sold_quantity = Column(Integer, default=0)
    
    # Relationships
    flash_sale = relationship("FlashSale", back_populates="products")
    product = relationship("Product", back_populates="flash_sale_products")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("sale_price > 0", name="check_positive_sale_price"),
        CheckConstraint("discount_percentage > 0 AND discount_percentage <= 100", name="check_valid_discount"),
        CheckConstraint("sale_quantity > 0", name="check_positive_sale_quantity"),
        CheckConstraint("sold_quantity >= 0", name="check_non_negative_sold"),
        Index("idx_flash_sale_products_sale_product", "flash_sale_id", "product_id"),
    )
    
    @property
    def is_available(self):
        """Check if product is still available in flash sale"""
        return self.sold_quantity < self.sale_quantity
