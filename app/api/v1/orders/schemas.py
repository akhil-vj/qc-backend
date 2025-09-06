"""
Order schemas for request/response validation
"""

from pydantic import BaseModel, Field, validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
import uuid

from app.models.order import OrderStatus

class OrderItemBase(BaseModel):
    """Base schema for order items"""
    product_id: uuid.UUID
    variant_id: Optional[uuid.UUID] = None
    quantity: int = Field(..., gt=0)

class OrderItemCreate(OrderItemBase):
    """Schema for creating order item"""
    pass

class OrderItemResponse(OrderItemBase):
    """Schema for order item response"""
    id: uuid.UUID
    product_name: str
    product_sku: Optional[str]
    variant_name: Optional[str]
    unit_price: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_price: Decimal
    is_reviewed: bool
    
    class Config:
        from_attributes = True

class AddressInfo(BaseModel):
    """Schema for address information"""
    recipient_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., pattern=r'^(\+91)?[6-9]\d{9}$')
    address_line1: str = Field(..., min_length=5, max_length=500)
    address_line2: Optional[str] = Field(None, max_length=500)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., pattern=r'^\d{6}$')
    country: str = Field("India", max_length=100)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

class OrderCreate(BaseModel):
    """Schema for creating order"""
    items: List[OrderItemCreate] = Field(..., min_items=1)
    shipping_address: AddressInfo
    billing_address: Optional[AddressInfo] = None
    payment_method: str = Field(..., pattern="^(cod|razorpay|upi|card|net_banking)$")
    coupon_code: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)
    
    @model_validator(mode='before')
    @classmethod
    def validate_addresses(cls, values):
        if not values.get('billing_address'):
            values['billing_address'] = values['shipping_address']
        return values

class OrderUpdate(BaseModel):
    """Schema for updating order"""
    status: Optional[OrderStatus] = None
    tracking_number: Optional[str] = Field(None, max_length=100)
    courier_partner: Optional[str] = Field(None, max_length=100)
    expected_delivery: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=500)

class OrderResponse(BaseModel):
    """Schema for order response"""
    id: uuid.UUID
    order_number: str
    buyer_id: uuid.UUID
    seller_id: uuid.UUID
    
    # Amounts
    subtotal: Decimal
    tax_amount: Decimal
    shipping_fee: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    
    # Status
    status: OrderStatus
    payment_status: str
    payment_method: Optional[str]
    
    # Addresses
    shipping_address: Dict[str, Any]
    billing_address: Optional[Dict[str, Any]]
    
    # Shipping
    shipping_method: Optional[str]
    tracking_number: Optional[str]
    courier_partner: Optional[str]
    expected_delivery: Optional[date]
    delivered_at: Optional[datetime]
    
    # Additional
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    # Related data
    items: List[OrderItemResponse]
    buyer_name: Optional[str] = None
    seller_name: Optional[str] = None
    can_cancel: bool = False
    can_return: bool = False
    
    class Config:
        from_attributes = True
        use_enum_values = True

class OrderListResponse(BaseModel):
    """Schema for paginated order list"""
    items: List[OrderResponse]
    total: int
    page: int
    size: int
    pages: int

class OrderCancelRequest(BaseModel):
    """Request to cancel order"""
    reason: str = Field(..., min_length=10, max_length=500)

class OrderReturnRequest(BaseModel):
    """Request to return order"""
    items: List[uuid.UUID] = Field(..., min_items=1)
    reason: str = Field(..., min_length=10, max_length=500)
    images: Optional[List[str]] = Field(None, max_items=5)

class OrderTrackingResponse(BaseModel):
    """Schema for order tracking information"""
    order_number: str
    status: OrderStatus
    tracking_number: Optional[str]
    courier_partner: Optional[str]
    expected_delivery: Optional[date]
    
    # Tracking events
    events: List[Dict[str, Any]] = []
    
    # Current location (if available)
    current_location: Optional[str] = None
    
    class Config:
        use_enum_values = True

class OrderInvoiceRequest(BaseModel):
    """Request to generate order invoice"""
    format: str = Field("pdf", pattern="^(pdf|html)$")

class OrderSummaryResponse(BaseModel):
    """Schema for order summary statistics"""
    total_orders: int
    pending_orders: int
    completed_orders: int
    cancelled_orders: int
    total_spent: Decimal
    total_saved: Decimal
    average_order_value: Decimal
