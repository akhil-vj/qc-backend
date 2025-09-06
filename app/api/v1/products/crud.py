"""
Product CRUD operations
Database operations for products
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
import uuid

from app.models import Product, ProductVariant, Category, Brand
from app.core.exceptions import NotFoundException

class ProductCRUD:
    """Product CRUD operations"""
    
    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        product_id: uuid.UUID,
        load_relations: bool = True
    ) -> Optional[Product]:
        """Get product by ID"""
        query = select(Product).where(Product.id == product_id)
        
        if load_relations:
            query = query.options(
                selectinload(Product.seller),
                selectinload(Product.category),
                selectinload(Product.brand),
                selectinload(Product.variants)
            )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_slug(
        db: AsyncSession,
        slug: str
    ) -> Optional[Product]:
        """Get product by slug"""
        result = await db.execute(
            select(Product).where(Product.slug == slug)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_sku(
        db: AsyncSession,
        sku: str
    ) -> Optional[Product]:
        """Get product by SKU"""
        result = await db.execute(
            select(Product).where(Product.sku == sku)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_multi(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Product]:
        """Get multiple products with filters"""
        query = select(Product)
        
        if filters:
            for key, value in filters.items():
                if hasattr(Product, key) and value is not None:
                    query = query.where(getattr(Product, key) == value)
        
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def create(
        db: AsyncSession,
        **kwargs
    ) -> Product:
        """Create new product"""
        product = Product(**kwargs)
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product
    
    @staticmethod
    async def update(
        db: AsyncSession,
        product: Product,
        **kwargs
    ) -> Product:
        """Update product"""
        for key, value in kwargs.items():
            if hasattr(product, key):
                setattr(product, key, value)
        
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product
    
    @staticmethod
    async def delete(
        db: AsyncSession,
        product: Product
    ) -> None:
        """Delete product"""
        await db.delete(product)
        await db.commit()
    
    @staticmethod
    async def count(
        db: AsyncSession,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """Count products with filters"""
        query = select(func.count()).select_from(Product)
        
        if filters:
            for key, value in filters.items():
                if hasattr(Product, key) and value is not None:
                    query = query.where(getattr(Product, key) == value)
        
        result = await db.execute(query)
        return result.scalar()
    
    @staticmethod
    async def update_search_vector(
        db: AsyncSession,
        product_id: uuid.UUID
    ) -> None:
        """Update product search vector for full-text search"""
        await db.execute(
            f"""
            UPDATE products 
            SET search_vector = to_tsvector('english', 
                COALESCE(title, '') || ' ' || 
                COALESCE(description, '') || ' ' || 
                COALESCE(array_to_string(tags, ' '), '')
            )
            WHERE id = '{product_id}'
            """
        )
        await db.commit()
