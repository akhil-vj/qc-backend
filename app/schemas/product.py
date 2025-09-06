"""Product Pydantic schemas"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
import uuid


class ProductBase(BaseModel):
    """Base product schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    price: Decimal = Field(..., gt=0)
    category_id: uuid.UUID
    brand_id: Optional[uuid.UUID] = None
    sku: Optional[str] = Field(None, max_length=100)
    slug: str = Field(..., min_length=1, max_length=255)
    is_active: bool = Field(default=True)
    is_featured: bool = Field(default=False)
    stock_quantity: int = Field(default=0, ge=0)
    weight: Optional[Decimal] = Field(None, gt=0)
    dimensions: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = Field(None, max_length=255)
    meta_description: Optional[str] = Field(None, max_length=500)

    @field_validator('price')
    @classmethod
    def validate_price(cls, v):
        if v is not None:
            # Ensure price has at most 2 decimal places
            return round(v, 2)
        return v


class ProductCreate(ProductBase):
    """Schema for creating a product"""
    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    price: Optional[Decimal] = Field(None, gt=0)
    category_id: Optional[uuid.UUID] = None
    brand_id: Optional[uuid.UUID] = None
    sku: Optional[str] = Field(None, max_length=100)
    slug: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    stock_quantity: Optional[int] = Field(None, ge=0)
    weight: Optional[Decimal] = Field(None, gt=0)
    dimensions: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = Field(None, max_length=255)
    meta_description: Optional[str] = Field(None, max_length=500)

    @field_validator('price')
    @classmethod
    def validate_price(cls, v):
        if v is not None:
            return round(v, 2)
        return v


class ProductResponse(ProductBase):
    """Schema for product response"""
    id: uuid.UUID
    category_id: Optional[uuid.UUID] = None  # Override to make optional
    slug: Optional[str] = None  # Override to make optional  
    view_count: Optional[int] = 0
    rating: Optional[Decimal] = None
    review_count: int = 0
    created_at: datetime
    updated_at: datetime
    
    # Category information
    category_name: Optional[str] = None
    category_slug: Optional[str] = None
    
    # Brand information
    brand_name: Optional[str] = None
    
    # Computed fields
    is_in_stock: bool = True
    
    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """Schema for paginated product list response"""
    items: List[ProductResponse]
    total: int
    page: int
    size: int
    pages: int


class ProductSearchResponse(BaseModel):
    """Schema for product search response"""
    items: List[ProductResponse]
    total: int
    query: str
    filters: Optional[Dict[str, Any]] = None


class ProductVariantBase(BaseModel):
    """Base product variant schema"""
    product_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    sku: Optional[str] = Field(None, max_length=100)
    price: Optional[Decimal] = Field(None, gt=0)
    stock_quantity: int = Field(default=0, ge=0)
    attributes: Optional[Dict[str, Any]] = None
    is_active: bool = Field(default=True)


class ProductVariantCreate(ProductVariantBase):
    """Schema for creating a product variant"""
    pass


class ProductVariantUpdate(BaseModel):
    """Schema for updating a product variant"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    sku: Optional[str] = Field(None, max_length=100)
    price: Optional[Decimal] = Field(None, gt=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    attributes: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ProductVariantResponse(ProductVariantBase):
    """Schema for product variant response"""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProductImageBase(BaseModel):
    """Base product image schema"""
    product_id: uuid.UUID
    url: str = Field(..., min_length=1)
    alt_text: Optional[str] = Field(None, max_length=255)
    is_primary: bool = Field(default=False)
    display_order: int = Field(default=0)


class ProductImageCreate(ProductImageBase):
    """Schema for creating a product image"""
    pass


class ProductImageUpdate(BaseModel):
    """Schema for updating a product image"""
    url: Optional[str] = Field(None, min_length=1)
    alt_text: Optional[str] = Field(None, max_length=255)
    is_primary: Optional[bool] = None
    display_order: Optional[int] = None


class ProductImageResponse(ProductImageBase):
    """Schema for product image response"""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
