"""Coin redemption endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.coin_service import CoinService

router = APIRouter(prefix="/coins/redeem", tags=["coin-redemption"])

class RedeemForDiscountRequest(BaseModel):
    order_id: str
    coins_to_redeem: int = Field(..., gt=0, le=10000)

class RedeemForCouponRequest(BaseModel):
    coupon_type: str = Field(..., pattern="^(flat_50|flat_100|percent_10|percent_20)$")

class ValidateRedemptionRequest(BaseModel):
    coins_to_redeem: int = Field(..., gt=0)
    redemption_type: str = Field(..., pattern="^(discount|coupon)$")

@router.post("/discount")
async def redeem_coins_for_discount(
    request: RedeemForDiscountRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Redeem coins for order discount"""
    service = CoinService(db)
    
    try:
        result = await service.redeem_coins_for_discount(
            user_id=current_user["id"],
            coins_to_redeem=request.coins_to_redeem,
            order_id=request.order_id
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/coupon")
async def redeem_coins_for_coupon(
    request: RedeemForCouponRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Redeem coins for a coupon"""
    service = CoinService(db)
    
    try:
        result = await service.redeem_coins_for_coupon(
            user_id=current_user["id"],
            coupon_type=request.coupon_type
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/validate")
async def validate_redemption(
    request: ValidateRedemptionRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Validate if coin redemption is possible"""
    service = CoinService(db)
    
    result = await service.validate_redemption(
        user_id=current_user["id"],
        coins_to_redeem=request.coins_to_redeem,
        redemption_type=request.redemption_type
    )
    
    return result

@router.get("/options")
async def get_redemption_options(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get available redemption options"""
    from app.models.user import User
    
    user = await db.get(User, current_user["id"])
    
    return {
        "current_balance": user.coin_balance,
        "discount_options": {
            "rate": "1 coin = ₹0.10",
            "max_discount_percentage": 20,
            "min_coins": 100,
            "max_coins": 10000
        },
        "coupon_options": [
            {
                "type": "flat_50",
                "name": "₹50 Off",
                "coins_required": 500,
                "description": "Get ₹50 off on your next order"
            },
            {
                "type": "flat_100",
                "name": "₹100 Off",
                "coins_required": 900,
                "description": "Get ₹100 off on your next order"
            },
            {
                "type": "percent_10",
                "name": "10% Off",
                "coins_required": 1000,
                "description": "Get 10% off on your next order"
            },
            {
                "type": "percent_20",
                "name": "20% Off",
                "coins_required": 1800,
                "description": "Get 20% off on your next order"
            }
        ]
    }
