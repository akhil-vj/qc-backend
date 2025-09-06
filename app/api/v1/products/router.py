"""Products API router"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.models import Product, Category
from app.schemas.product import ProductResponse, ProductListResponse

router = APIRouter()


@router.get("/", response_model=ProductListResponse)
async def get_products(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of items to return"),
    db: AsyncSession = Depends(get_db)
):
    """Get products with pagination"""
    
    try:
        # Simple query - just get all active products
        query = select(Product).where(Product.status == 'active').offset(skip).limit(limit)
        result = await db.execute(query)
        products = result.scalars().all()
        
        # Count total
        count_query = select(func.count(Product.id)).where(Product.status == 'active')
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Calculate pagination
        pages = (total + limit - 1) // limit if total > 0 else 0
        page = (skip // limit) + 1
        
        return ProductListResponse(
            items=products,
            total=total,
            page=page,
            size=limit,
            pages=pages
        )
    except Exception as e:
        print(f"Error in get_products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/featured", response_model=ProductListResponse)
async def get_featured_products(
    limit: int = Query(10, ge=1, le=100, description="Number of items to return"),
    db: AsyncSession = Depends(get_db)
):
    """Get featured products"""
    
    try:
        query = select(Product).where(
            and_(Product.status == 'active', Product.is_featured == True)
        ).limit(limit)
        
        result = await db.execute(query)
        products = result.scalars().all()
        
        # Count total featured products
        count_query = select(func.count(Product.id)).where(
            and_(Product.status == 'active', Product.is_featured == True)
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        return ProductListResponse(
            items=products,
            total=total,
            page=1,
            size=limit,
            pages=1
        )
    except Exception as e:
        print(f"Error in get_featured_products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending", response_model=ProductListResponse)
async def get_trending_products(
    limit: int = Query(10, ge=1, le=100, description="Number of items to return"),
    db: AsyncSession = Depends(get_db)
):
    """Get trending products (most viewed/sold recently)"""
    
    try:
        # For now, just return recent products with high view counts
        query = select(Product).where(Product.status == 'active').order_by(
            desc(Product.view_count), desc(Product.created_at)
        ).limit(limit)
        
        result = await db.execute(query)
        products = result.scalars().all()
        
        return ProductListResponse(
            items=products,
            total=len(products),
            page=1,
            size=limit,
            pages=1
        )
    except Exception as e:
        print(f"Error in get_trending_products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=ProductListResponse)
async def search_products(
    q: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None, description="Category filter"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    sort_by: Optional[str] = Query("relevance", description="Sort by: relevance, price_asc, price_desc, rating, newest"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    db: AsyncSession = Depends(get_db)
):
    """Search products with filters and sorting"""
    
    try:
        # Build search query
        base_query = select(Product).where(Product.status == 'active')
        
        # Apply search filter
        if q:
            search_filter = or_(
                Product.name.ilike(f"%{q}%"),
                Product.description.ilike(f"%{q}%")
            )
            base_query = base_query.where(search_filter)
        
        # Apply category filter
        if category:
            category_query = select(Category).where(Category.name.ilike(f"%{category}%"))
            category_result = await db.execute(category_query)
            category_obj = category_result.scalar_one_or_none()
            if category_obj:
                base_query = base_query.where(Product.category_id == category_obj.id)
        
        # Apply price filters
        if min_price is not None:
            base_query = base_query.where(Product.price >= min_price)
        if max_price is not None:
            base_query = base_query.where(Product.price <= max_price)
        
        # Apply sorting
        if sort_by == "price_asc":
            base_query = base_query.order_by(asc(Product.price))
        elif sort_by == "price_desc":
            base_query = base_query.order_by(desc(Product.price))
        elif sort_by == "rating":
            base_query = base_query.order_by(desc(Product.rating))
        elif sort_by == "newest":
            base_query = base_query.order_by(desc(Product.created_at))
        else:  # relevance (default)
            # For relevance, we can order by view_count and rating
            base_query = base_query.order_by(desc(Product.view_count), desc(Product.rating))
        
        # Get total count for pagination
        count_query = select(func.count(Product.id)).where(Product.status == 'active')
        if q:
            search_filter = or_(
                Product.name.ilike(f"%{q}%"),
                Product.description.ilike(f"%{q}%")
            )
            count_query = count_query.where(search_filter)
        
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        paginated_query = base_query.offset(skip).limit(limit)
        result = await db.execute(paginated_query)
        products = result.scalars().all()
        
        # Calculate pagination info
        pages = (total + limit - 1) // limit if total > 0 else 0
        page = (skip // limit) + 1
        
        return ProductListResponse(
            items=products,
            total=total,
            page=page,
            size=limit,
            pages=pages
        )
        
    except Exception as e:
        print(f"Error in search_products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product_by_id(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get product by ID"""
    
    try:
        query = select(Product).where(
            and_(Product.id == product_id, Product.status == 'active')
        )
        result = await db.execute(query)
        product = result.scalar_one_or_none()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return product
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_product_by_id: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/slug/{slug}", response_model=ProductResponse)
async def get_product_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db)
):
    """Get product by slug"""
    
    try:
        query = select(Product).where(
            and_(Product.slug == slug, Product.status == 'active')
        )
        result = await db.execute(query)
        product = result.scalar_one_or_none()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return product
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_product_by_slug: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{product_id}/similar", response_model=ProductListResponse)
async def get_similar_products(
    product_id: uuid.UUID,
    limit: int = Query(8, ge=1, le=20, description="Number of similar products to return"),
    db: AsyncSession = Depends(get_db)
):
    """Get similar products based on category and brand"""
    
    try:
        # First get the current product
        current_product_query = select(Product).where(
            and_(Product.id == product_id, Product.status == 'active')
        )
        current_result = await db.execute(current_product_query)
        current_product = current_result.scalar_one_or_none()
        
        if not current_product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Find similar products based on category and brand
        similar_query = select(Product).where(
            and_(
                Product.status == 'active',
                Product.id != product_id,  # Exclude current product
                or_(
                    Product.category_id == current_product.category_id,  # Same category
                    Product.brand_id == current_product.brand_id  # Same brand
                )
            )
        ).order_by(desc(Product.rating), desc(Product.view_count)).limit(limit)
        
        result = await db.execute(similar_query)
        products = result.scalars().all()
        
        return ProductListResponse(
            items=products,
            total=len(products),
            page=1,
            size=limit,
            pages=1
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_similar_products: {e}")
        raise HTTPException(status_code=500, detail=str(e))
