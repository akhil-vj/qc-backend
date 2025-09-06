"""Rewards API router for QuickCart"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.models.user import User

router = APIRouter()

# User rewards endpoints
@router.get("/balance")
async def get_user_points_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's current points balance"""
    try:
        # Mock balance - would fetch from database
        balance = {
            "user_id": current_user.id,
            "total_points": 1250,
            "available_points": 1000,
            "pending_points": 250,
            "points_expires_soon": 100,
            "expiry_date": "2025-12-31T23:59:59Z"
        }
        return balance
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get points balance: {str(e)}"
        )

@router.get("/history")
async def get_points_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's points transaction history"""
    try:
        # Mock history - would fetch from database
        history = [
            {
                "id": 1,
                "type": "earned",
                "points": 50,
                "description": "Purchase order #1234",
                "date": "2025-08-12T10:30:00Z",
                "order_id": 1234
            },
            {
                "id": 2,
                "type": "redeemed",
                "points": -100,
                "description": "Discount on order #1235",
                "date": "2025-08-11T15:45:00Z",
                "order_id": 1235
            }
        ]
        return {"history": history, "total": len(history)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get points history: {str(e)}"
        )

@router.get("/programs")
async def get_reward_programs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get available reward programs"""
    try:
        programs = [
            {
                "id": 1,
                "name": "Purchase Points",
                "description": "Earn 1 point for every $1 spent",
                "points_rate": 1.0,
                "is_active": True
            },
            {
                "id": 2,
                "name": "Referral Bonus",
                "description": "Earn 500 points for each successful referral",
                "points_reward": 500,
                "is_active": True
            },
            {
                "id": 3,
                "name": "Review Rewards",
                "description": "Earn 25 points for each product review",
                "points_reward": 25,
                "is_active": True
            }
        ]
        return {"programs": programs, "total": len(programs)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get reward programs: {str(e)}"
        )

@router.get("/redemption-options")
async def get_redemption_options(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get available point redemption options"""
    try:
        options = [
            {
                "id": 1,
                "type": "discount",
                "name": "$5 Off Coupon",
                "description": "Get $5 off your next purchase",
                "points_required": 500,
                "value": 5.00,
                "is_available": True
            },
            {
                "id": 2,
                "type": "discount",
                "name": "$10 Off Coupon",
                "description": "Get $10 off your next purchase",
                "points_required": 1000,
                "value": 10.00,
                "is_available": True
            },
            {
                "id": 3,
                "type": "free_shipping",
                "name": "Free Shipping",
                "description": "Free shipping on your next order",
                "points_required": 200,
                "is_available": True
            }
        ]
        return {"options": options, "total": len(options)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get redemption options: {str(e)}"
        )

@router.post("/redeem/{option_id}")
async def redeem_points(
    option_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Redeem points for a reward"""
    try:
        # Mock redemption - would process actual redemption
        redemption = {
            "id": 123,
            "user_id": current_user.id,
            "option_id": option_id,
            "points_used": 500,
            "reward_type": "discount",
            "reward_value": 5.00,
            "coupon_code": "SAVE5-ABC123",
            "expires_at": "2025-09-13T23:59:59Z",
            "redeemed_at": "2025-08-13T10:30:00Z"
        }
        return {
            "message": "Points redeemed successfully",
            "redemption": redemption
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to redeem points: {str(e)}"
        )

# Admin endpoints for rewards management
@router.get("/admin/stats")
async def get_rewards_stats(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get rewards program statistics (Admin only)"""
    try:
        stats = {
            "total_points_issued": 50000,
            "total_points_redeemed": 35000,
            "active_users_with_points": 1250,
            "most_popular_redemption": "$5 Off Coupon",
            "total_redemptions_this_month": 145,
            "average_points_per_user": 40
        }
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get rewards stats: {str(e)}"
        )

@router.get("/admin/users")
async def get_users_points_summary(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get users points summary (Admin only)"""
    try:
        users = [
            {
                "user_id": 1,
                "email": "user1@example.com",
                "total_points": 1250,
                "available_points": 1000,
                "total_earned": 2500,
                "total_redeemed": 1500,
                "last_activity": "2025-08-12T10:30:00Z"
            },
            {
                "user_id": 2,
                "email": "user2@example.com",
                "total_points": 750,
                "available_points": 750,
                "total_earned": 1200,
                "total_redeemed": 450,
                "last_activity": "2025-08-10T14:20:00Z"
            }
        ]
        return {"users": users, "total": len(users)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get users points summary: {str(e)}"
        )

@router.post("/admin/adjust-points/{user_id}")
async def adjust_user_points(
    user_id: int,
    points: int,
    reason: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Adjust user points balance (Admin only)"""
    try:
        adjustment = {
            "user_id": user_id,
            "points_adjustment": points,
            "reason": reason,
            "adjusted_by": current_user.id,
            "adjusted_at": "2025-08-13T10:30:00Z"
        }
        return {
            "message": "Points adjusted successfully",
            "adjustment": adjustment
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to adjust points: {str(e)}"
        )

@router.get("/health")
async def rewards_health_check():
    """Rewards API health check"""
    return {"status": "healthy", "module": "rewards"}
