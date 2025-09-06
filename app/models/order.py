"""Order model with state machine"""

from sqlalchemy import Column, String, Numeric, Integer, Enum, ForeignKey, Index, Text, DateTime, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from .base import Base, TimestampedModel, UUIDModel, AuditModel

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    FAILED = "failed"
    RETURN_REQUESTED = "return_requested"
    RETURN_APPROVED = "return_approved"
    RETURN_REJECTED = "return_rejected"
    RETURN_PICKED = "return_picked"
    RETURNED = "returned"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"

class Order(Base, TimestampedModel, UUIDModel, AuditModel):
    """Order model with audit support"""
    
    __tablename__ = "orders"
    
    # Order identification
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    
    # Parties
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Status
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False, index=True)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    
    # Amounts
    subtotal = Column(Numeric(10, 2), nullable=False)
    delivery_fee = Column(Numeric(10, 2), default=0)
    tax_amount = Column(Numeric(10, 2), default=0)
    discount_amount = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2), nullable=False)
    
    # Payment
    payment_method = Column(String(50), nullable=False)
    payment_reference = Column(String(200))
    
    # Addresses
    shipping_address_id = Column(UUID(as_uuid=True), ForeignKey("addresses.id"))
    billing_address_id = Column(UUID(as_uuid=True), ForeignKey("addresses.id"))
    shipping_address = Column(JSONB, nullable=False)  # keeping for compatibility
    billing_address = Column(JSONB, nullable=True)    # keeping for compatibility
    
    # Delivery
    delivery_type = Column(String(50), default="standard")
    shipping_method = Column(String(100), nullable=True)  # keeping for compatibility
    tracking_number = Column(String(100))
    carrier = Column(String(100))
    courier_partner = Column(String(100), nullable=True)  # keeping for compatibility
    estimated_delivery = Column(DateTime(timezone=True))
    actual_delivery = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True), nullable=True)  # keeping for compatibility
    
    # Timestamps
    confirmed_at = Column(DateTime(timezone=True))
    shipped_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    
    # Additional info
    notes = Column(Text, nullable=True)
    internal_notes = Column(Text)
    cancellation_reason = Column(String(500))
    order_metadata = Column(JSON, default={})
    
    # Relationships
    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="orders_as_buyer")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="orders_as_seller")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    status_history = relationship("OrderStatusHistory", back_populates="order", cascade="all, delete-orphan")
    payment = relationship("Payment", back_populates="order", uselist=False)  # keeping for compatibility
    reviews = relationship("Review", back_populates="order")  # keeping for compatibility
    coin_redemption = relationship("CoinRedemption", back_populates="order", uselist=False)
    
    # Indexes
    __table_args__ = (
        Index("idx_orders_buyer_status", "buyer_id", "status"),
        Index("idx_orders_seller_status", "seller_id", "status"),
        Index("idx_orders_created_status", "created_at", "status"),
        Index("idx_orders_payment_status", "payment_status"),
    )

class OrderItem(Base, TimestampedModel, UUIDModel):
    """Individual items within an order"""
    
    __tablename__ = "order_items"
    
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    
    # Item details (snapshot at time of order)
    product_name = Column(String(500), nullable=False)
    product_sku = Column(String(100), nullable=True)
    variant_name = Column(String(255), nullable=True)
    
    # Quantities and pricing
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    discount_amount = Column(Numeric(10, 2), default=0)
    tax_amount = Column(Numeric(10, 2), default=0)
    total_price = Column(Numeric(10, 2), nullable=False)
    
    # Status
    is_reviewed = Column(Boolean, default=False)
    
    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    
    # Constraints
    __table_args__ = (
        Index("idx_order_items_order_product", "order_id", "product_id"),
    )

class OrderStatusHistory(Base, TimestampedModel, UUIDModel):
    """Track order status changes"""
    
    __tablename__ = "order_status_history"
    
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    status = Column(Enum(OrderStatus), nullable=False)
    previous_status = Column(Enum(OrderStatus), nullable=True)
    reason = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    order = relationship("Order", back_populates="status_history")
    changed_by_user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_order_status_history_order", "order_id"),
        Index("idx_order_status_history_status", "status"),
    )
