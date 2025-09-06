"""
Category CRUD operations
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update, delete, func, and_, or_
from typing import Optional, List, Dict, Any
import uuid

from app.models import Category, Product
from app.schemas.category import CategoryCreate, CategoryUpdate


async def get_category_by_id(db: AsyncSession, category_id: uuid.UUID) -> Optional[Category]:
    """Get category by ID"""
    stmt = (
        select(Category)
        .options(
            selectinload(Category.parent),
            selectinload(Category.children)
        )
        .where(Category.id == category_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_category_by_slug(db: AsyncSession, slug: str) -> Optional[Category]:
    """Get category by slug"""
    stmt = (
        select(Category)
        .options(
            selectinload(Category.parent),
            selectinload(Category.children)
        )
        .where(Category.slug == slug)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_categories(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    parent_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None
) -> List[Category]:
    """Get categories with filters"""
    stmt = select(Category).options(
        selectinload(Category.parent),
        selectinload(Category.children)
    )
    
    # Apply filters
    conditions = []
    
    if parent_id is not None:
        conditions.append(Category.parent_id == parent_id)
    
    if is_active is not None:
        conditions.append(Category.is_active == is_active)
    
    if search:
        conditions.append(
            or_(
                Category.name.ilike(f"%{search}%"),
                Category.description.ilike(f"%{search}%")
            )
        )
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    stmt = stmt.order_by(Category.display_order, Category.name).offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_categories_count(
    db: AsyncSession,
    parent_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None
) -> int:
    """Get count of categories with filters"""
    stmt = select(func.count(Category.id))
    
    conditions = []
    
    if parent_id is not None:
        conditions.append(Category.parent_id == parent_id)
    
    if is_active is not None:
        conditions.append(Category.is_active == is_active)
    
    if search:
        conditions.append(
            or_(
                Category.name.ilike(f"%{search}%"),
                Category.description.ilike(f"%{search}%")
            )
        )
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    result = await db.execute(stmt)
    return result.scalar()


async def get_root_categories(db: AsyncSession, is_active: bool = True) -> List[Category]:
    """Get root categories (categories with no parent)"""
    stmt = (
        select(Category)
        .options(selectinload(Category.children))
        .where(Category.parent_id.is_(None))
    )
    
    if is_active:
        stmt = stmt.where(Category.is_active == True)
    
    stmt = stmt.order_by(Category.display_order, Category.name)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_category_tree(db: AsyncSession, is_active: bool = True) -> List[Category]:
    """Get complete category tree"""
    # Get all categories with their relationships
    stmt = (
        select(Category)
        .options(
            selectinload(Category.parent),
            selectinload(Category.children)
        )
    )
    
    if is_active:
        stmt = stmt.where(Category.is_active == True)
    
    stmt = stmt.order_by(Category.display_order, Category.name)
    
    result = await db.execute(stmt)
    all_categories = list(result.scalars().all())
    
    # Build tree structure
    root_categories = [cat for cat in all_categories if cat.parent_id is None]
    
    return root_categories


async def create_category(db: AsyncSession, category: CategoryCreate) -> Category:
    """Create new category"""
    db_category = Category(**category.model_dump())
    db.add(db_category)
    await db.commit()
    await db.refresh(db_category)
    
    # Load relationships
    await db.refresh(db_category, ['parent', 'children'])
    
    return db_category


async def update_category(
    db: AsyncSession, 
    category_id: uuid.UUID, 
    category_update: CategoryUpdate
) -> Optional[Category]:
    """Update category"""
    # Check if category exists
    category = await get_category_by_id(db, category_id)
    if not category:
        return None
    
    # Update fields
    update_data = category_update.model_dump(exclude_unset=True)
    if update_data:
        stmt = (
            update(Category)
            .where(Category.id == category_id)
            .values(**update_data)
        )
        await db.execute(stmt)
        await db.commit()
        
        # Refresh and return updated category
        await db.refresh(category)
        await db.refresh(category, ['parent', 'children'])
    
    return category


async def delete_category(db: AsyncSession, category_id: uuid.UUID) -> bool:
    """Delete category (only if no products or children)"""
    # Check if category has children
    children_count = await db.execute(
        select(func.count(Category.id)).where(Category.parent_id == category_id)
    )
    if children_count.scalar() > 0:
        return False
    
    # Check if category has products
    products_count = await db.execute(
        select(func.count(Product.id)).where(Product.category_id == category_id)
    )
    if products_count.scalar() > 0:
        return False
    
    # Delete category
    stmt = delete(Category).where(Category.id == category_id)
    result = await db.execute(stmt)
    await db.commit()
    
    return result.rowcount > 0


async def get_category_stats(db: AsyncSession) -> Dict[str, Any]:
    """Get category statistics"""
    # Total categories
    total_stmt = select(func.count(Category.id))
    total_result = await db.execute(total_stmt)
    total_categories = total_result.scalar()
    
    # Active categories
    active_stmt = select(func.count(Category.id)).where(Category.is_active == True)
    active_result = await db.execute(active_stmt)
    active_categories = active_result.scalar()
    
    # Root categories
    root_stmt = select(func.count(Category.id)).where(Category.parent_id.is_(None))
    root_result = await db.execute(root_stmt)
    root_categories = root_result.scalar()
    
    # Categories with products
    categories_with_products_stmt = select(func.count(func.distinct(Product.category_id)))
    categories_with_products_result = await db.execute(categories_with_products_stmt)
    categories_with_products = categories_with_products_result.scalar()
    
    # Average products per category
    avg_products_stmt = select(func.avg(func.count(Product.id))).select_from(Product).group_by(Product.category_id)
    avg_products_result = await db.execute(avg_products_stmt)
    avg_products = avg_products_result.scalar() or 0
    
    return {
        "total_categories": total_categories,
        "active_categories": active_categories,
        "inactive_categories": total_categories - active_categories,
        "root_categories": root_categories,
        "categories_with_products": categories_with_products,
        "average_products_per_category": float(avg_products),
    }


async def get_category_with_product_count(db: AsyncSession, category_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Get category with product count"""
    category = await get_category_by_id(db, category_id)
    if not category:
        return None
    
    # Get product count
    product_count_stmt = select(func.count(Product.id)).where(Product.category_id == category_id)
    product_count_result = await db.execute(product_count_stmt)
    product_count = product_count_result.scalar() or 0
    
    # Get children count
    children_count_stmt = select(func.count(Category.id)).where(Category.parent_id == category_id)
    children_count_result = await db.execute(children_count_stmt)
    children_count = children_count_result.scalar() or 0
    
    return {
        "category": category,
        "product_count": product_count,
        "children_count": children_count
    }


async def check_slug_exists(db: AsyncSession, slug: str, exclude_id: Optional[uuid.UUID] = None) -> bool:
    """Check if slug already exists"""
    stmt = select(Category.id).where(Category.slug == slug)
    
    if exclude_id:
        stmt = stmt.where(Category.id != exclude_id)
    
    result = await db.execute(stmt)
    return result.scalar() is not None


async def bulk_create_categories(db: AsyncSession, categories: List[CategoryCreate]) -> List[Category]:
    """Bulk create categories"""
    db_categories = []
    
    for category_data in categories:
        db_category = Category(**category_data.model_dump())
        db.add(db_category)
        db_categories.append(db_category)
    
    await db.commit()
    
    # Refresh all categories
    for category in db_categories:
        await db.refresh(category)
        await db.refresh(category, ['parent', 'children'])
    
    return db_categories


async def reorder_categories(db: AsyncSession, category_orders: List[Dict[str, Any]]) -> bool:
    """Reorder categories by updating display_order"""
    try:
        for order_data in category_orders:
            category_id = order_data.get('id')
            display_order = order_data.get('display_order')
            
            if category_id and display_order is not None:
                stmt = (
                    update(Category)
                    .where(Category.id == category_id)
                    .values(display_order=display_order)
                )
                await db.execute(stmt)
        
        await db.commit()
        return True
    except Exception:
        await db.rollback()
        return False
