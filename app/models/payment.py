"""
Payment model for transaction handling
Integrates with payment gateways
"""

from sqlalchemy import Column, String, Numeric, ForeignKey, Index, Enum, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
import enum

from .base import Base, TimestampedModel

class PaymentStatus(str, enum.Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"

class PaymentMethod(str, enum.Enum):
    """Payment method enumeration"""
    CARD = "card"
    UPI = "upi"
    NET_BANKING = "net_banking"
    WALLET = "wallet"
    COD = "cod"
    RAZORPAY = "razorpay"

class Payment(Base, TimestampedModel):
    """Payment transaction records"""
    
    __tablename__ = "payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), unique=True, nullable=False)
    
    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    method = Column(Enum(PaymentMethod), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    
    # Gateway details
    gateway_transaction_id = Column(String(255), nullable=True)
    gateway_payment_id = Column(String(255), nullable=True)
    gateway_order_id = Column(String(255), nullable=True)
    gateway_signature = Column(String(500), nullable=True)
    
    # Timestamps
    processed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional data
    payment_metadata = Column(JSONB, default={})
    failure_reason = Column(Text, nullable=True)
    refund_amount = Column(Numeric(10, 2), default=0)
    
    # Relationships
    order = relationship("Order", back_populates="payment")
    
    # Indexes
    __table_args__ = (
        Index("idx_payments_status", "status"),
        Index("idx_payments_method", "method"),
        Index("idx_payments_gateway_transaction", "gateway_transaction_id"),
        Index("idx_payments_processed_at", "processed_at"),
    )
    
    def __str__(self):
        return f"Payment {self.id} - {self.amount} {self.currency} ({self.status})"
