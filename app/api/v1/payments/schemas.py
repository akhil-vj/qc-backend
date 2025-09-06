"""
Payment schemas for request/response validation
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
import uuid

from app.models.payment import PaymentStatus, PaymentMethod

class PaymentInitiate(BaseModel):
    """Schema for initiating payment"""
    order_id: uuid.UUID
    payment_method: PaymentMethod
    
    class Config:
        use_enum_values = True

class PaymentVerify(BaseModel):
    """Schema for verifying payment"""
    order_id: uuid.UUID
    payment_id: str = Field(..., description="Payment ID from gateway")
    payment_signature: str = Field(..., description="Payment signature from gateway")

class PaymentResponse(BaseModel):
    """Schema for payment response"""
    id: uuid.UUID
    order_id: uuid.UUID
    amount: Decimal
    currency: str
    payment_method: PaymentMethod
    gateway_payment_id: Optional[str]
    gateway_order_id: Optional[str]
    status: PaymentStatus
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        use_enum_values = True

class PaymentInitiateResponse(BaseModel):
    """Response for payment initiation"""
    payment_id: uuid.UUID
    gateway_order_id: str
    amount: Decimal
    currency: str
    
    # Razorpay specific
    key_id: Optional[str] = None
    
    # Additional options for frontend
    options: Dict[str, Any] = {}
    
    class Config:
        json_schema_extra = {
            "example": {
                "payment_id": "123e4567-e89b-12d3-a456-426614174000",
                "gateway_order_id": "order_ABC123DEF456",
                "amount": 1000.00,
                "currency": "INR",
                "key_id": "rzp_test_1234567890",
                "options": {
                    "name": "QuickCart",
                    "description": "Order Payment",
                    "prefill": {
                        "name": "John Doe",
                        "email": "john@example.com",
                        "contact": "+919876543210"
                    }
                }
            }
        }

class RefundRequest(BaseModel):
    """Request for payment refund"""
    reason: str = Field(..., min_length=10, max_length=500)
    amount: Optional[Decimal] = Field(None, gt=0, description="Partial refund amount")

class RefundResponse(BaseModel):
    """Response for refund request"""
    refund_id: str
    payment_id: uuid.UUID
    amount: Decimal
    status: str
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "refund_id": "rfnd_ABC123DEF456",
                "payment_id": "123e4567-e89b-12d3-a456-426614174000",
                "amount": 1000.00,
                "status": "processed",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }

class PaymentWebhook(BaseModel):
    """Schema for payment webhook from gateway"""
    entity: str
    event: str
    contains: list[str]
    payload: Dict[str, Any]
    created_at: int

class PaymentHistoryResponse(BaseModel):
    """Schema for payment history"""
    payments: list[PaymentResponse]
    total: int
    page: int
    size: int
    pages: int

class PaymentMethodResponse(BaseModel):
    """Schema for available payment methods"""
    method: PaymentMethod
    name: str
    description: str
    icon: Optional[str]
    is_available: bool
    min_amount: Optional[Decimal]
    max_amount: Optional[Decimal]
    
    class Config:
        use_enum_values = True
