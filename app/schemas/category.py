"""
Category schemas for request/response validation
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import uuid


class CategoryBase(BaseModel):
    """Base schema for categories"""
    name: str = Field(..., min_length=2, max_length=100, description="Category name")
    slug: str = Field(..., min_length=2, max_length=100, description="URL-friendly slug")
    parent_id: Optional[uuid.UUID] = Field(None, description="Parent category ID")
    icon: Optional[str] = Field(None, max_length=255, description="Icon URL or class")
    image: Optional[str] = Field(None, max_length=500, description="Category image URL")
    description: Optional[str] = Field(None, max_length=1000, description="Category description")
    display_order: int = Field(default=0, description="Display order for sorting")
    is_active: bool = Field(default=True, description="Whether category is active")
    meta_title: Optional[str] = Field(None, max_length=255, description="SEO meta title")
    meta_description: Optional[str] = Field(None, max_length=1000, description="SEO meta description")

    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v):
        """Validate slug format"""
        import re
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        return v


class CategoryCreate(CategoryBase):
    """Schema for creating category"""
    pass


class CategoryUpdate(BaseModel):
    """Schema for updating category"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    slug: Optional[str] = Field(None, min_length=2, max_length=100)
    parent_id: Optional[uuid.UUID] = None
    icon: Optional[str] = Field(None, max_length=255)
    image: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=1000)
    display_order: Optional[int] = None
    is_active: Optional[bool] = None
    meta_title: Optional[str] = Field(None, max_length=255)
    meta_description: Optional[str] = Field(None, max_length=1000)

    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v):
        """Validate slug format"""
        if v is not None:
            import re
            if not re.match(r'^[a-z0-9-]+$', v):
                raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        return v


class CategoryResponse(CategoryBase):
    """Schema for category response"""
    id: uuid.UUID
    full_path: str
    product_count: int = Field(default=0, description="Number of products in this category")
    children_count: int = Field(default=0, description="Number of child categories")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CategoryWithChildren(CategoryResponse):
    """Schema for category with children"""
    children: List['CategoryWithChildren'] = Field(default=[], description="Child categories")
    parent: Optional['CategoryResponse'] = Field(None, description="Parent category")


class CategoryTree(BaseModel):
    """Schema for category tree structure"""
    categories: List[CategoryWithChildren]


class CategoryListResponse(BaseModel):
    """Schema for paginated category list"""
    items: List[CategoryResponse]
    total: int
    page: int
    size: int
    pages: int


class CategoryBulkCreate(BaseModel):
    """Schema for bulk category creation"""
    categories: List[CategoryCreate]


class CategoryBulkUpdate(BaseModel):
    """Schema for bulk category update"""
    categories: List[dict]  # {id: uuid, updates: CategoryUpdate}


class CategoryStats(BaseModel):
    """Schema for category statistics"""
    total_categories: int
    active_categories: int
    inactive_categories: int
    root_categories: int
    categories_with_products: int
    average_products_per_category: float


# Enable forward references
CategoryWithChildren.model_rebuild()
