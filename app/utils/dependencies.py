"""
Common dependencies for FastAPI
"""

from typing import Optional
from fastapi import Query, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User
from .pagination import PaginationParams

def get_pagination_params(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size")
) -> PaginationParams:
    """Get pagination parameters from query"""
    return PaginationParams(page=page, size=size)

async def get_current_active_user(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current active user from database
    
    Args:
        current_user: Current user from JWT
        db: Database session
        
    Returns:
        User model instance
        
    Raises:
        HTTPException: If user not found or inactive
    """
    result = await db.execute(
        select(User).where(
            User.id == current_user["id"],
            User.is_active == True
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or inactive"
        )
    
    return user

async def get_optional_current_user(
    current_user: Optional[dict] = Depends(get_current_user),
    db: Optional[AsyncSession] = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise"""
    if not current_user:
        return None
    
    try:
        result = await db.execute(
            select(User).where(User.id == current_user["id"])
        )
        return result.scalar_one_or_none()
    except Exception:
        return None
