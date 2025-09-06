"""Payment schemas for request/response models."""

from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.payment import PaymentStatus, PaymentMethod


class PaymentBase(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: str = Field(default="INR", description="Payment currency")
    method: PaymentMethod = Field(description="Payment method")


class PaymentCreate(PaymentBase):
    order_id: str = Field(..., description="Order ID")


class PaymentUpdate(BaseModel):
    status: Optional[PaymentStatus] = None
    gateway_payment_id: Optional[str] = None
    gateway_order_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PaymentResponse(PaymentBase):
    id: str
    order_id: str
    status: PaymentStatus
    gateway_payment_id: Optional[str] = None
    gateway_order_id: Optional[str] = None
    refund_amount: Optional[Decimal] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaymentOrderCreate(BaseModel):
    order_id: str = Field(..., description="Order ID")
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: str = Field(default="INR", description="Payment currency")


class PaymentOrderResponse(BaseModel):
    payment_id: str
    razorpay_order_id: str
    razorpay_key_id: str
    amount: Decimal
    currency: str
    order_id: str


class PaymentVerification(BaseModel):
    payment_id: str = Field(..., description="Internal payment ID")
    razorpay_payment_id: str = Field(..., description="Razorpay payment ID")
    razorpay_signature: str = Field(..., description="Razorpay signature")


class RefundRequest(BaseModel):
    payment_id: str = Field(..., description="Payment ID to refund")
    amount: Optional[Decimal] = Field(None, gt=0, description="Refund amount (full refund if not specified)")
    reason: str = Field(default="Customer request", description="Refund reason")


class RefundResponse(BaseModel):
    refund_id: str
    amount: Decimal
    status: str


class WebhookEvent(BaseModel):
    event: str
    payload: Dict[str, Any]
    created_at: int
