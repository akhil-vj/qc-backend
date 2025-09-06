"""
Cart schemas for request/response validation
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
import uuid


class CartItemBase(BaseModel):
    """Base schema for cart items"""
    product_id: int = Field(..., description="Product ID")
    variant_id: Optional[int] = Field(None, description="Product variant ID")
    quantity: int = Field(..., ge=1, description="Quantity")


class CartItemCreate(CartItemBase):
    """Schema for creating cart item"""
    pass


class CartItemUpdate(BaseModel):
    """Schema for updating cart item"""
    quantity: int = Field(..., ge=1, description="New quantity")


class CartItemResponse(CartItemBase):
    """Schema for cart item response"""
    id: int
    user_id: int
    product_name: str
    product_image: Optional[str] = None
    unit_price: Decimal
    total_price: Decimal
    variant_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CartTotals(BaseModel):
    """Schema for cart totals"""
    subtotal: Decimal
    tax: Decimal
    shipping: Decimal
    discount: Decimal = Field(default=0)
    total: Decimal
    total_items: int


class CartResponse(BaseModel):
    """Schema for cart response"""
    items: List[CartItemResponse]
    totals: CartTotals
    item_count: int

    class Config:
        from_attributes = True


class AddToCartRequest(BaseModel):
    """Schema for add to cart request"""
    product_id: int = Field(..., description="Product ID")
    variant_id: Optional[int] = Field(None, description="Product variant ID")
    quantity: int = Field(default=1, ge=1, description="Quantity to add")


class CouponValidationRequest(BaseModel):
    """Schema for coupon validation request"""
    coupon_code: str = Field(..., description="Coupon code to validate")
    order_amount: Decimal = Field(..., ge=0, description="Order amount for validation")


class CouponValidationResponse(BaseModel):
    """Schema for coupon validation response"""
    valid: bool
    discount_amount: Optional[Decimal] = None
    coupon_code: Optional[str] = None
    error: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[Decimal] = None

    class Config:
        from_attributes = True
