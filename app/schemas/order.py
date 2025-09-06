"""Order schemas for request/response models."""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.order import OrderStatus


class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    variant_id: Optional[str] = None
    quantity: int
    price: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    product_title: str
    product_image: Optional[str] = None

    class Config:
        from_attributes = True


class OrderBase(BaseModel):
    payment_method: str = Field(..., description="Payment method")
    shipping_address_id: str = Field(..., description="Shipping address ID")
    billing_address_id: Optional[str] = Field(None, description="Billing address ID")
    notes: Optional[str] = Field(None, max_length=500, description="Order notes")
    coupon_code: Optional[str] = Field(None, description="Coupon code")


class OrderCreate(OrderBase):
    pass


class OrderUpdate(BaseModel):
    shipping_address: Optional[str] = Field(None, description="Updated shipping address")
    billing_address: Optional[str] = Field(None, description="Updated billing address")
    notes: Optional[str] = Field(None, description="Updated order notes")


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., description="New order status")
    tracking_info: Optional[Dict[str, Any]] = Field(None, description="Tracking information")


class OrderResponse(OrderBase):
    id: str
    order_number: str
    status: OrderStatus
    buyer_id: str
    seller_id: str
    subtotal: Decimal
    delivery_fee: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    payment_status: Optional[str] = None
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    estimated_delivery: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    
    # Order items
    items: List[OrderItemResponse] = []
    
    # Address information
    shipping_address: Optional[Dict[str, Any]] = None
    billing_address: Optional[Dict[str, Any]] = None
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class OrderSummary(BaseModel):
    id: str
    order_number: str
    status: OrderStatus
    total_amount: Decimal
    created_at: datetime
    items_count: int

    class Config:
        from_attributes = True


class OrderStats(BaseModel):
    total_orders: int
    pending_orders: int
    confirmed_orders: int
    shipped_orders: int
    delivered_orders: int
    cancelled_orders: int
    total_revenue: Decimal
    average_order_value: Decimal


class ReturnRequest(BaseModel):
    order_id: str = Field(..., description="Order ID to return")
    reason: str = Field(..., description="Reason for return")
    items: List[str] = Field(..., description="List of item IDs to return")
    refund_amount: Optional[Decimal] = Field(None, description="Requested refund amount")
    notes: Optional[str] = Field(None, description="Additional notes for return request")

    class Config:
        from_attributes = True
