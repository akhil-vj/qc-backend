"""
Cart schemas for request/response validation
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import uuid

class CartItemBase(BaseModel):
    """Base schema for cart items"""
    product_id: uuid.UUID
    variant_id: Optional[uuid.UUID] = None
    quantity: int = Field(1, gt=0)

class CartItemCreate(CartItemBase):
    """Schema for adding item to cart"""
    pass

class CartItemUpdate(BaseModel):
    """Schema for updating cart item"""
    quantity: int = Field(..., gt=0)

class CartItemResponse(CartItemBase):
    """Schema for cart item response"""
    id: uuid.UUID
    price: Decimal
    saved_for_later: bool
    created_at: datetime
    
    # Product details
    product_title: str
    product_slug: str
    product_thumbnail: Optional[str]
    product_price: Decimal
    product_final_price: Decimal
    product_stock: int
    variant_name: Optional[str] = None
    
    # Calculated fields
    subtotal: Decimal
    is_available: bool
    
    class Config:
        from_attributes = True

class CartResponse(BaseModel):
    """Schema for complete cart response"""
    items: List[CartItemResponse]
    saved_items: List[CartItemResponse]
    
    # Summary
    total_items: int
    subtotal: Decimal
    discount: Decimal = Decimal("0.00")
    tax: Decimal = Decimal("0.00")
    shipping_fee: Decimal = Decimal("0.00")
    total: Decimal
    
    # Applied coupon
    applied_coupon: Optional[str] = None
    coupon_discount: Decimal = Decimal("0.00")
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "saved_items": [],
                "total_items": 0,
                "subtotal": "0.00",
                "discount": "0.00",
                "tax": "0.00",
                "shipping_fee": "0.00",
                "total": "0.00",
                "applied_coupon": None,
                "coupon_discount": "0.00"
            }
        }

class MoveToCartRequest(BaseModel):
    """Request to move item from saved to cart"""
    item_id: uuid.UUID

class ApplyCouponRequest(BaseModel):
    """Request to apply coupon to cart"""
    coupon_code: str = Field(..., min_length=3, max_length=50)

class CartMergeRequest(BaseModel):
    """Request to merge session cart with user cart"""
    session_id: str = Field(..., min_length=10, max_length=255)
