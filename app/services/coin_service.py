"""Coin management service"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import uuid

from app.models.user import User
from app.models.coin_transaction import CoinTransaction, CoinRedemption
from app.models.order import Order
from app.core.exceptions import BadRequestException, NotFoundException

class CoinService:
    """Service for managing coin transactions and redemptions"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def award_coins(
        self,
        user_id: str,
        amount: int,
        source: str,
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None
    ) -> CoinTransaction:
        """Award coins to a user"""
        user = await self.db.get(User, user_id)
        if not user:
            raise NotFoundException("User not found")
            
        # Calculate new balance
        new_balance = (user.coin_balance or 0) + amount
        
        # Create transaction
        transaction = CoinTransaction(
            user_id=user_id,
            amount=amount,
            balance_after=new_balance,
            transaction_type="earned",
            source=source,
            reference_id=reference_id,
            description=description,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None
        )
        
        # Update user balance
        user.coin_balance = new_balance
        
        self.db.add(transaction)
        await self.db.commit()
        
        return transaction
        
    async def redeem_coins_for_discount(
        self,
        user_id: str,
        coins_to_redeem: int,
        order_id: str
    ) -> Dict[str, Any]:
        """Redeem coins for order discount"""
        # Validate user and balance
        user = await self.db.get(User, user_id)
        if not user:
            raise NotFoundException("User not found")
            
        if user.coin_balance < coins_to_redeem:
            raise BadRequestException("Insufficient coin balance")
            
        # Validate order
        order = await self.db.get(Order, order_id)
        if not order:
            raise NotFoundException("Order not found")
            
        if order.buyer_id != user_id:
            raise BadRequestException("Order does not belong to user")
            
        if order.status != "pending":
            raise BadRequestException("Cannot apply discount to non-pending order")
            
        # Calculate discount (1 coin = ₹0.10)
        discount_amount = coins_to_redeem * 0.10
        max_discount = float(order.subtotal) * 0.20  # Max 20% discount
        
        if discount_amount > max_discount:
            discount_amount = max_discount
            coins_to_redeem = int(max_discount / 0.10)
            
        # Create redemption record
        redemption = CoinRedemption(
            user_id=user_id,
            coins_redeemed=coins_to_redeem,
            redemption_type="discount",
            discount_amount=discount_amount,
            order_id=order_id,
            status="applied"
        )
        
        # Create transaction
        new_balance = user.coin_balance - coins_to_redeem
        transaction = CoinTransaction(
            user_id=user_id,
            amount=-coins_to_redeem,
            balance_after=new_balance,
            transaction_type="spent",
            source="order_discount",
            reference_id=str(order_id),
            description=f"Discount on order {order.order_number}"
        )
        
        # Update user balance
        user.coin_balance = new_balance
        
        # Update order
        order.coin_discount = discount_amount
        order.total_amount = order.subtotal + order.shipping_fee + order.tax - discount_amount
        
        self.db.add(redemption)
        self.db.add(transaction)
        await self.db.commit()
        
        return {
            "success": True,
            "coins_redeemed": coins_to_redeem,
            "discount_amount": discount_amount,
            "new_balance": new_balance,
            "redemption_id": str(redemption.id)
        }
        
    async def redeem_coins_for_coupon(
        self,
        user_id: str,
        coupon_type: str
    ) -> Dict[str, Any]:
        """Redeem coins for a coupon"""
        # Define coupon types and costs
        coupon_config = {
            "flat_50": {"coins": 500, "value": 50, "description": "₹50 off coupon"},
            "flat_100": {"coins": 900, "value": 100, "description": "₹100 off coupon"},
            "percent_10": {"coins": 1000, "value": 10, "description": "10% off coupon"},
            "percent_20": {"coins": 1800, "value": 20, "description": "20% off coupon"},
        }
        
        if coupon_type not in coupon_config:
            raise BadRequestException("Invalid coupon type")
            
        config = coupon_config[coupon_type]
        
        # Validate user and balance
        user = await self.db.get(User, user_id)
        if not user:
            raise NotFoundException("User not found")
            
        if user.coin_balance < config["coins"]:
            raise BadRequestException("Insufficient coin balance")
            
        # Generate coupon code
        import random
        import string
        coupon_code = ''.join(random.choices(string.ASCII_UPPERCASE + string.digits, k=8))
        
        # Create redemption
        redemption = CoinRedemption(
            user_id=user_id,
            coins_redeemed=config["coins"],
            redemption_type="coupon",
            coupon_code=coupon_code,
            status="pending"
        )
        
        # Create transaction
        new_balance = user.coin_balance - config["coins"]
        transaction = CoinTransaction(
            user_id=user_id,
            amount=-config["coins"],
            balance_after=new_balance,
            transaction_type="spent",
            source="coupon_redemption",
            reference_id=coupon_code,
            description=config["description"]
        )
        
        # Update user balance
        user.coin_balance = new_balance
        
        # Create coupon in coupons table
        # Create coupon in coupons table
        from app.models.coupon import Coupon
        
        coupon = Coupon(
            code=coupon_code,
            discount_type="flat" if "flat" in coupon_type else "percentage",
            discount_value=config["value"],
            minimum_order_amount=200,  # Min order ₹200
            max_uses=1,
            valid_from=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(days=30),
            created_by=user_id,
            is_coin_redemption=True
        )
        
        self.db.add(redemption)
        self.db.add(transaction)
        self.db.add(coupon)
        await self.db.commit()
        
        return {
            "success": True,
            "coupon_code": coupon_code,
            "coupon_value": config["value"],
            "coupon_type": coupon_type,
            "valid_until": coupon.valid_until,
            "new_balance": new_balance
        }
        
    async def validate_redemption(
        self,
        user_id: str,
        coins_to_redeem: int,
        redemption_type: str
    ) -> Dict[str, Any]:
        """Validate if redemption is possible"""
        user = await self.db.get(User, user_id)
        if not user:
            raise NotFoundException("User not found")
            
        if user.coin_balance < coins_to_redeem:
            return {
                "valid": False,
                "error": "Insufficient coin balance",
                "current_balance": user.coin_balance,
                "required": coins_to_redeem
            }
            
        # Check for daily redemption limits
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        stmt = select(func.sum(CoinRedemption.coins_redeemed)).where(
            and_(
                CoinRedemption.user_id == user_id,
                CoinRedemption.created_at >= today_start
            )
        )
        
        daily_redeemed = await self.db.scalar(stmt) or 0
        daily_limit = 5000  # Max 5000 coins per day
        
        if daily_redeemed + coins_to_redeem > daily_limit:
            return {
                "valid": False,
                "error": "Daily redemption limit exceeded",
                "daily_limit": daily_limit,
                "already_redeemed_today": daily_redeemed
            }
            
        return {
            "valid": True,
            "current_balance": user.coin_balance,
            "coins_to_redeem": coins_to_redeem
        }
