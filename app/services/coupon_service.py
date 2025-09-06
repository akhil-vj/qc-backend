"""
Coupon service for managing discount coupons
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.coupon import Coupon, CouponUsage
from app.models.user import User
from app.core.exceptions import NotFoundException, BadRequestException


class CouponService:
    """
    Service for managing coupon operations
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def validate_coupon(
        self, 
        code: str, 
        user_id: int, 
        order_amount: float
    ) -> Dict[str, Any]:
        """
        Validate coupon and calculate discount
        """
        try:
            # Get coupon by code
            result = await self.db.execute(
                select(Coupon).where(
                    and_(
                        Coupon.code == code.upper(),
                        Coupon.is_active == True,
                        Coupon.start_date <= datetime.utcnow(),
                        Coupon.end_date >= datetime.utcnow()
                    )
                )
            )
            coupon = result.scalar_one_or_none()
            
            if not coupon:
                return {
                    "valid": False,
                    "error": "Invalid or expired coupon code"
                }
            
            # Check usage limits
            if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
                return {
                    "valid": False,
                    "error": "Coupon usage limit exceeded"
                }
            
            # Check per-user usage limit
            if coupon.per_user_limit:
                usage_result = await self.db.execute(
                    select(CouponUsage).where(
                        and_(
                            CouponUsage.coupon_id == coupon.id,
                            CouponUsage.user_id == user_id
                        )
                    )
                )
                user_usage_count = len(usage_result.scalars().all())
                
                if user_usage_count >= coupon.per_user_limit:
                    return {
                        "valid": False,
                        "error": "You have already used this coupon maximum times"
                    }
            
            # Check minimum order amount
            if coupon.minimum_amount and order_amount < coupon.minimum_amount:
                return {
                    "valid": False,
                    "error": f"Minimum order amount of ₹{coupon.minimum_amount} required"
                }
            
            # Calculate discount
            if coupon.discount_type == "percentage":
                discount_amount = (order_amount * coupon.discount_value) / 100
                if coupon.maximum_discount:
                    discount_amount = min(discount_amount, coupon.maximum_discount)
            else:  # fixed amount
                discount_amount = min(coupon.discount_value, order_amount)
            
            return {
                "valid": True,
                "coupon_id": coupon.id,
                "discount_amount": discount_amount,
                "coupon_code": coupon.code,
                "discount_type": coupon.discount_type,
                "discount_value": coupon.discount_value
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Error validating coupon: {str(e)}"
            }
    
    async def apply_coupon(
        self, 
        coupon_id: int, 
        user_id: int, 
        order_id: int,
        discount_amount: float
    ) -> bool:
        """
        Apply coupon and record usage
        """
        try:
            # Create coupon usage record
            usage = CouponUsage(
                coupon_id=coupon_id,
                user_id=user_id,
                order_id=order_id,
                discount_amount=discount_amount,
                used_at=datetime.utcnow()
            )
            self.db.add(usage)
            
            # Update coupon used count
            coupon_result = await self.db.execute(
                select(Coupon).where(Coupon.id == coupon_id)
            )
            coupon = coupon_result.scalar_one_or_none()
            
            if coupon:
                coupon.used_count += 1
            
            await self.db.commit()
            return True
            
        except Exception:
            await self.db.rollback()
            return False
    
    async def get_available_coupons(self, user_id: int) -> list:
        """
        Get all available coupons for user
        """
        try:
            result = await self.db.execute(
                select(Coupon).where(
                    and_(
                        Coupon.is_active == True,
                        Coupon.start_date <= datetime.utcnow(),
                        Coupon.end_date >= datetime.utcnow()
                    )
                ).order_by(Coupon.discount_value.desc())
            )
            return result.scalars().all()
            
        except Exception:
            return []
    
    async def get_coupon_by_code(self, code: str) -> Optional[Coupon]:
        """
        Get coupon by code
        """
        try:
            result = await self.db.execute(
                select(Coupon).where(Coupon.code == code.upper())
            )
            return result.scalar_one_or_none()
            
        except Exception:
            return None
