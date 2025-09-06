"""
Pagination utilities
"""

from typing import TypeVar, Generic, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

T = TypeVar('T')

class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Page size")
    
    @property
    def offset(self) -> int:
        """Calculate offset"""
        return (self.page - 1) * self.size

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response"""
    items: List[T]
    total: int
    page: int
    size: int
    pages: int
    
    @property
    def has_next(self) -> bool:
        """Check if has next page"""
        return self.page < self.pages
    
    @property
    def has_prev(self) -> bool:
        """Check if has previous page"""
        return self.page > 1

async def paginate(
    db: AsyncSession,
    query: Select,
    page: int = 1,
    size: int = 20
) -> dict:
    """
    Paginate query results
    
    Args:
        db: Database session
        query: SQLAlchemy query
        page: Page number
        size: Page size
        
    Returns:
        Dictionary with pagination data
    """
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Calculate pages
    pages = (total + size - 1) // size
    
    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)
    
    # Execute query
    result = await db.execute(query)
    items = result.scalars().all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }
