"""
Category API router with proper None handling for display_order
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.models.category import Category
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryWithChildren,
    CategoryTree,
    CategoryListResponse
)

router = APIRouter()


async def _get_category_with_counts(db: AsyncSession, category: Category) -> dict:
    """Get category with product and children counts"""
    
    # Count child categories
    children_count_query = select(func.count()).where(Category.parent_id == category.id)
    children_count_result = await db.execute(children_count_query)
    children_count = children_count_result.scalar() or 0
    
    return {
        "product_count": 0,  # Placeholder - would need Product model import
        "children_count": children_count
    }


def _category_to_response(category: Category, product_count: int = 0, children_count: int = 0) -> dict:
    """Convert category model to response dict with proper None handling"""
    
    # Convert category to dict, excluding SQLAlchemy internals
    category_dict = {k: v for k, v in category.__dict__.items() 
                    if not k.startswith('_') and k not in ['children', 'parent', 'products']}
    
    # Handle None values for required fields - THIS IS THE KEY FIX
    if category_dict.get('display_order') is None:
        category_dict['display_order'] = 0
    
    # Add computed fields
    category_dict.update({
        'full_path': category.full_path,
        'product_count': product_count,
        'children_count': children_count
    })
    
    return category_dict


@router.get("/tree", response_model=CategoryTree)
async def get_category_tree(
    is_active: bool = Query(True, description="Filter by active status"),
    db: AsyncSession = Depends(get_db)
):
    """Get complete category tree structure"""
    
    try:
        # Get all categories with their relationships
        query = select(Category).where(Category.is_active == is_active if is_active else True)
        result = await db.execute(query)
        all_categories = result.scalars().all()
        
        # Build tree structure starting with root categories (no parent)
        root_categories = [cat for cat in all_categories if cat.parent_id is None]
        
        async def build_category_tree(categories: List[Category]) -> List[CategoryWithChildren]:
            """Recursively build category tree"""
            result = []
            
            for category in categories:
                # Get counts for this category
                counts = await _get_category_with_counts(db, category)
                
                # Convert to response format with None handling
                category_data = _category_to_response(
                    category, 
                    counts["product_count"], 
                    counts["children_count"]
                )
                
                # Create response object
                category_response = CategoryWithChildren(**category_data, children=[])
                
                # Find and add children recursively
                children = [cat for cat in all_categories if cat.parent_id == category.id]
                if children:
                    category_response.children = await build_category_tree(children)
                
                result.append(category_response)
            
            # Sort by display_order
            result.sort(key=lambda x: x.display_order)
            return result
        
        # Build the tree
        category_tree = await build_category_tree(root_categories)
        
        return CategoryTree(categories=category_tree)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error building category tree: {str(e)}"
        )


@router.get("/", response_model=CategoryListResponse)
async def get_categories(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of items to return"),
    parent_id: Optional[uuid.UUID] = Query(None, description="Filter by parent category ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search categories by name or description"),
    db: AsyncSession = Depends(get_db)
):
    """Get categories with pagination and filtering"""
    
    try:
        # Build query conditions
        conditions = []
        if parent_id is not None:
            conditions.append(Category.parent_id == parent_id)
        if is_active is not None:
            conditions.append(Category.is_active == is_active)
        if search:
            search_term = f"%{search}%"
            conditions.append(or_(
                Category.name.ilike(search_term),
                Category.description.ilike(search_term)
            ))
        
        # Get categories with pagination
        query = select(Category)
        if conditions:
            query = query.where(and_(*conditions))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get paginated results
        query = query.order_by(Category.display_order, Category.name).offset(skip).limit(limit)
        result = await db.execute(query)
        categories = result.scalars().all()
        
        # Convert to response format
        category_responses = []
        for category in categories:
            counts = await _get_category_with_counts(db, category)
            category_data = _category_to_response(
                category, 
                counts["product_count"], 
                counts["children_count"]
            )
            category_response = CategoryResponse(**category_data)
            category_responses.append(category_response)
        
        pages = (total + limit - 1) // limit if limit > 0 else 1
        
        return CategoryListResponse(
            items=category_responses,
            total=total,
            page=(skip // limit) + 1 if limit > 0 else 1,
            size=limit,
            pages=pages
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting categories: {str(e)}"
        )


@router.get("/{category_id}", response_model=CategoryWithChildren)
async def get_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get category by ID with children"""
    
    try:
        # Get category
        query = select(Category).where(Category.id == category_id)
        result = await db.execute(query)
        category = result.scalar_one_or_none()
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        
        # Get counts for this category
        counts = await _get_category_with_counts(db, category)
        
        # Convert to response format with None handling
        category_data = _category_to_response(
            category, 
            counts["product_count"], 
            counts["children_count"]
        )
        
        # Create response object
        category_response = CategoryWithChildren(**category_data, children=[])
        
        # Get children
        children_query = select(Category).where(Category.parent_id == category_id)
        children_result = await db.execute(children_query)
        children = children_result.scalars().all()
        
        # Add children to response
        for child in children:
            child_counts = await _get_category_with_counts(db, child)
            child_data = _category_to_response(
                child, 
                child_counts["product_count"], 
                child_counts["children_count"]
            )
            child_response = CategoryWithChildren(**child_data, children=[])
            category_response.children.append(child_response)
        
        # Sort children by display_order
        category_response.children.sort(key=lambda x: x.display_order)
        
        return category_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting category: {str(e)}"
        )
