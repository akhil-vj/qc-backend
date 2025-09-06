"""Coin management service"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
import uuid

from app.models import User, CoinTransaction, CoinReward, Order
from app.services.notification import NotificationService

class CoinService:
    """Service for managing coin transactions"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notification_service = NotificationService(db)
        
    async def award_coins(
        self,
        user_id: str,
        amount: int,
        reason: str,
        description: Optional[str] = None,
        reference_id: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        awarded_by: Optional[str] = None
    ) -> CoinTransaction:
        """Award coins to user"""
        # Get user
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
            
        # Check daily limit for this reason
        if await self._check_daily_limit(user_id, reason):
            raise ValueError("Daily limit reached for this reward")
            
        # Create transaction
        transaction = CoinTransaction(
            user_id=user_id,
            amount=amount,
            transaction_type="earned",
            reason=reason,
            description=description,
            reference_id=reference_id,
            balance_after=user.coin_balance + amount,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None,
            awarded_by=awarded_by
        )
        
        # Update user balance
        user.coin_balance += amount
        
        self.db.add(transaction)
        await self.db.commit()
        
        # Send notification
        await self.notification_service.create_notification(
            user_id=user_id,
            title="Coins Earned!",
            message=f"You've earned {amount} coins for {reason}",
            type="coins_earned",
            metadata={"amount": amount, "reason": reason}
        )
        
        return transaction
        
    async def redeem_coins(
        self,
        user_id: str,
        amount: int,
        order_id: Optional[str] = None,
        reward_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Redeem coins for discount or rewards"""
        # Get user
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
            
        # Check balance
        if user.coin_balance < amount:
            raise ValueError("Insufficient coin balance")
            
        # Calculate discount (1 coin = ₹0.10)
        discount_amount = Decimal(amount * 0.10)
        
        # Create transaction
        transaction = CoinTransaction(
            user_id=user_id,
            amount=-amount,
            transaction_type="spent",
            reason="order_discount" if order_id else "reward_redemption",
            reference_id=order_id or reward_id,
            balance_after=user.coin_balance - amount
        )
        
        # Update user balance
        user.coin_balance -= amount
        
        # If order redemption, update order
        if order_id:
            order = await self.db.get(Order, order_id)
            if order:
                order.coin_discount = discount_amount
                order.coins_used = amount
                
        self.db.add(transaction)
        await self.db.commit()
        
        return {
            "transaction_id": str(transaction.id),
            "new_balance": user.coin_balance,
            "discount_amount": discount_amount
        }
        
    async def process_referral_reward(
        self,
        referrer_id: str,
        referred_id: str
    ):
        """Process referral rewards"""
        # Award coins to referrer
        await self.award_coins(
            user_id=referrer_id,
            amount=100,
            reason="referral",
            description=f"Referred a new user",
            reference_id=referred_id
        )
        
        # Award coins to referred user
        await self.award_coins(
            user_id=referred_id,
            amount=50,
            reason="referral_bonus",
            description="Welcome bonus from referral",
            reference_id=referrer_id
        )
        
    async def process_review_reward(
        self,
        user_id: str,
        review_id: str,
        has_photo: bool = False
    ):
        """Process review rewards"""
        amount = 20
        if has_photo:
            amount = 50
            
        await self.award_coins(
            user_id=user_id,
            amount=amount,
            reason="review",
            description="Product review" + (" with photo" if has_photo else ""),
            reference_id=review_id
        )
        
    async def process_daily_checkin(self, user_id: str) -> Dict[str, Any]:
        """Process daily check-in rewards"""
        # Check if already checked in today
        today = datetime.utcnow().date()
        existing = await self.db.execute(
            select(CoinTransaction).where(
                and_(
                    CoinTransaction.user_id == user_id,
                    CoinTransaction.reason == "daily_checkin",
                    func.date(CoinTransaction.created_at) == today
                )
            )
        )
        
        if existing.scalar():
            raise ValueError("Already checked in today")
            
        # Get user's streak
        user = await self.db.get(User, user_id)
        
        # Check if streak continues
        yesterday = today - timedelta(days=1)
        yesterday_checkin = await self.db.execute(
            select(CoinTransaction).where(
                and_(
                    CoinTransaction.user_id == user_id,
                    CoinTransaction.reason == "daily_checkin",
                    func.date(CoinTransaction.created_at) == yesterday
                )
            )
        )
        
        if yesterday_checkin.scalar():
            user.checkin_streak += 1
        else:
            user.checkin_streak = 1
            
        # Calculate reward based on streak
        base_reward = 5
        streak_bonus = min(user.checkin_streak - 1, 10) * 2
        total_reward = base_reward + streak_bonus
        
        # Award coins
        await self.award_coins(
            user_id=user_id,
            amount=total_reward,
            reason="daily_checkin",
            description=f"Daily check-in (Day {user.checkin_streak})"
        )
        
        await self.db.commit()
        
        return {
            "coins_earned": total_reward,
            "streak": user.checkin_streak,
            "next_bonus_at": 7 if user.checkin_streak < 7 else None
        }
        
    async def expire_coins(self):
        """Expire old coins (run as cron job)"""
        # Find expired coins
        expired = await self.db.execute(
            select(CoinTransaction).where(
                and_(
                    CoinTransaction.expires_at != None,
                    CoinTransaction.expires_at <= datetime.utcnow(),
                    CoinTransaction.is_expired == False,
                    CoinTransaction.transaction_type == "earned"
                )
            )
        )
        
        for transaction in expired.scalars().all():
            # Mark as expired
            transaction.is_expired = True
            
            # Deduct from user balance
            user = await self.db.get(User, transaction.user_id)
            if user and user.coin_balance >= transaction.amount:
                user.coin_balance -= transaction.amount
                
                # Create expiry transaction
                expiry_transaction = CoinTransaction(
                    user_id=transaction.user_id,
                    amount=-transaction.amount,
                    transaction_type="expired",
                    reason="coin_expiry",
                    reference_id=str(transaction.id),
                    balance_after=user.coin_balance
                )
                self.db.add(expiry_transaction)
                
        await self.db.commit()
        
    async def _check_daily_limit(self, user_id: str, reason: str) -> bool:
        """Check if daily limit reached for reward type"""
        # Get reward config
        reward_config = await self.db.execute(
            select(CoinReward).where(CoinReward.action == reason)
        )
        config = reward_config.scalar()
        
        if not config or not config.max_per_day:
            return False
            
        # Count today's transactions
        today = datetime.utcnow().date()
        count = await self.db.scalar(
            select(func.count()).select_from(CoinTransaction).where(
                and_(
                    CoinTransaction.user_id == user_id,
                    CoinTransaction.reason == reason,
                    func.date(CoinTransaction.created_at) == today
                )
            )
        )
        
        return count >= config.max_per_day
