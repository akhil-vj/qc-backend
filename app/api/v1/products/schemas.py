"""
Product schemas for request/response validation
"""

from pydantic import BaseModel, Field, validator, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
import uuid

class ProductVariantBase(BaseModel):
    """Base schema for product variants"""
    name: str = Field(..., min_length=1, max_length=255)
    attributes: Dict[str, Any] = Field(..., description="Variant attributes like color, size")
    price: Optional[Decimal] = Field(None, ge=0)
    mrp: Optional[Decimal] = Field(None, ge=0)
    stock: int = Field(0, ge=0)
    image: Optional[HttpUrl] = None
    is_active: bool = True

class ProductVariantCreate(ProductVariantBase):
    """Schema for creating product variant"""
    sku: Optional[str] = Field(None, max_length=100)

class ProductVariantUpdate(BaseModel):
    """Schema for updating product variant"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    attributes: Optional[Dict[str, Any]] = None
    price: Optional[Decimal] = Field(None, ge=0)
    mrp: Optional[Decimal] = Field(None, ge=0)
    stock: Optional[int] = Field(None, ge=0)
    image: Optional[HttpUrl] = None
    is_active: Optional[bool] = None

class ProductVariantResponse(ProductVariantBase):
    """Schema for product variant response"""
    id: uuid.UUID
    sku: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ProductImageBase(BaseModel):
    """Base schema for product images"""
    url: HttpUrl
    alt_text: Optional[str] = Field(None, max_length=255)
    display_order: int = Field(0, ge=0)
    is_primary: bool = False

class ProductBase(BaseModel):
    """Base schema for products"""
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None
    price: Decimal = Field(..., ge=0)
    mrp: Optional[Decimal] = Field(None, ge=0)
    category_id: Optional[uuid.UUID] = None
    brand_id: Optional[uuid.UUID] = None
    tags: List[str] = []
    
    # Inventory
    stock: int = Field(0, ge=0)
    min_order_quantity: int = Field(1, ge=1)
    max_order_quantity: Optional[int] = Field(None, ge=1)
    track_inventory: bool = True
    
    # Details
    weight: Optional[Decimal] = Field(None, ge=0)
    dimensions: Optional[Dict[str, float]] = None
    
    # Policies
    shipping_info: Dict[str, Any] = {}
    return_policy: Dict[str, Any] = {}
    warranty_info: Dict[str, Any] = {}
    
    # Flags
    is_featured: bool = False
    is_digital: bool = False
    
    @validator('mrp')
    def validate_mrp(cls, v, values):
        if v and 'price' in values and v < values['price']:
            raise ValueError('MRP cannot be less than selling price')
        return v
    
    @validator('max_order_quantity')
    def validate_max_order(cls, v, values):
        if v and 'min_order_quantity' in values and v < values['min_order_quantity']:
            raise ValueError('Max order quantity cannot be less than min order quantity')
        return v

class ProductCreate(ProductBase):
    """Schema for creating product"""
    sku: Optional[str] = Field(None, max_length=100)
    thumbnail: Optional[HttpUrl] = None
    images: List[ProductImageBase] = []
    variants: List[ProductVariantCreate] = []
    status: str = Field("draft", pattern="^(draft|active|inactive)$")

class ProductUpdate(BaseModel):
    """Schema for updating product"""
    title: Optional[str] = Field(None, min_length=3, max_length=500)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    mrp: Optional[Decimal] = Field(None, ge=0)
    discount_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    category_id: Optional[uuid.UUID] = None
    brand_id: Optional[uuid.UUID] = None
    tags: Optional[List[str]] = None
    thumbnail: Optional[HttpUrl] = None
    stock: Optional[int] = Field(None, ge=0)
    min_order_quantity: Optional[int] = Field(None, ge=1)
    max_order_quantity: Optional[int] = Field(None, ge=1)
    status: Optional[str] = Field(None, pattern="^(draft|active|inactive|out_of_stock)$")
    is_featured: Optional[bool] = None

class ProductResponse(ProductBase):
    """Schema for product response"""
    id: uuid.UUID
    seller_id: uuid.UUID
    sku: Optional[str]
    slug: str
    thumbnail: Optional[str]
    images: List[Dict[str, Any]]
    discount_percentage: Optional[Decimal]
    status: str
    view_count: int
    purchase_count: int
    ai_category_suggestion: Optional[str]
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    final_price: Decimal
    is_in_stock: bool
    
    # Related data
    seller_name: Optional[str] = None
    category_name: Optional[str] = None
    brand_name: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: int = 0
    variants: List[ProductVariantResponse] = []
    
    class Config:
        from_attributes = True

class ProductListResponse(BaseModel):
    """Schema for paginated product list"""
    items: List[ProductResponse]
    total: int
    page: int
    size: int
    pages: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "size": 20,
                "pages": 5
            }
        }

class ProductSearchRequest(BaseModel):
    """Schema for product search"""
    query: str = Field(..., min_length=1, max_length=500)
    category_id: Optional[uuid.UUID] = None
    brand_id: Optional[uuid.UUID] = None
    min_price: Optional[Decimal] = Field(None, ge=0)
    max_price: Optional[Decimal] = Field(None, ge=0)
    tags: Optional[List[str]] = None
    in_stock: Optional[bool] = None
    sort_by: str = Field("relevance", pattern="^(relevance|price_asc|price_desc|newest|popular)$")
    
    @validator('max_price')
    def validate_price_range(cls, v, values):
        if v and 'min_price' in values and values['min_price'] and v < values['min_price']:
            raise ValueError('Max price cannot be less than min price')
        return v

class BulkUploadRequest(BaseModel):
    """Schema for bulk product upload"""
    products: List[ProductCreate]
    
    @validator('products')
    def validate_products_count(cls, v):
        if len(v) > 100:
            raise ValueError('Cannot upload more than 100 products at once')
        return v

class ProductStockUpdate(BaseModel):
    """Schema for updating product stock"""
    stock: int = Field(..., ge=0)
    variant_id: Optional[uuid.UUID] = None

class ProductReviewBase(BaseModel):
    """Base schema for product reviews"""
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = Field(None, max_length=255)
    comment: Optional[str] = None
    images: List[HttpUrl] = []

class ProductReviewCreate(ProductReviewBase):
    """Schema for creating product review"""
    order_id: Optional[uuid.UUID] = None

class ProductReviewResponse(ProductReviewBase):
    """Schema for product review response"""
    id: uuid.UUID
    product_id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    user_image: Optional[str]
    is_verified_purchase: bool
    helpful_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProductComparisonRequest(BaseModel):
    """Schema for product comparison"""
    product_ids: List[uuid.UUID] = Field(..., min_items=2, max_items=4)

class ProductRecommendationResponse(BaseModel):
    """Schema for product recommendations"""
    recommended_products: List[ProductResponse]
    recommendation_type: str  # similar, frequently_bought, trending
