"""Analytics API routes"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import date, timedelta

from app.core.database import get_db
from app.core.security import get_current_user, require_seller
from .schemas import (
    DateRangeFilter,
    SalesAnalytics,
    SellerDashboardAnalytics,
    UserBehaviorTracking
)
from .services import AnalyticsService

router = APIRouter()

@router.get(
    "/sales",
    response_model=SalesAnalytics,
    summary="Get sales analytics"
)
async def get_sales_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: dict = Depends(require_seller),
    db: AsyncSession = Depends(get_db)
):
    """Get sales analytics for seller"""
    service = AnalyticsService(db)
    
    date_range = None
    if start_date and end_date:
        date_range = DateRangeFilter(start_date=start_date, end_date=end_date)
    
    return await service.get_sales_analytics(
        seller_id=current_user["id"],
        date_range=date_range
    )

@router.get(
    "/dashboard",
    response_model=SellerDashboardAnalytics,
    summary="Get seller dashboard analytics"
)
async def get_dashboard_analytics(
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(require_seller),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive dashboard analytics"""
    service = AnalyticsService(db)
    
    date_range = DateRangeFilter(
        start_date=date.today() - timedelta(days=days),
        end_date=date.today()
    )
    
    return await service.get_seller_dashboard_analytics(
        seller_id=current_user["id"],
        date_range=date_range
    )

@router.post(
    "/track",
    summary="Track user behavior"
)
async def track_user_behavior(
    event: UserBehaviorTracking,
    current_user: Optional[dict] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Track user behavior events"""
    service = AnalyticsService(db)
    
    event_data = event.dict()
    if current_user:
        event_data["user_id"] = current_user["id"]
    
    await service.track_user_behavior(event_data)
    
    return {"status": "tracked"}

@router.get(
    "/products/performance",
    summary="Get product performance"
)
async def get_product_performance(
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(require_seller),
    db: AsyncSession = Depends(get_db)
):
    """Get top performing products"""
    service = AnalyticsService(db)
    
    products = await service.get_product_performance(
        seller_id=current_user["id"],
        limit=limit
    )
    
    return {"products": products}

@router.get(
    "/customers",
    summary="Get customer analytics"
)
async def get_customer_analytics(
    current_user: dict = Depends(require_seller),
    db: AsyncSession = Depends(get_db)
):
    """Get customer analytics"""
    service = AnalyticsService(db)
    
    analytics = await service.get_customer_analytics(
        seller_id=current_user["id"]
    )
    
    return analytics
