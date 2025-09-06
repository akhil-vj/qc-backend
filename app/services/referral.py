"""Referral system service"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import uuid

from app.models import User, ReferralTracking, ReferralMilestone, UserReferralMilestone
from app.services.coins import CoinService
from app.services.notification import NotificationService

class ReferralService:
    """Service for managing referrals"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.coin_service = CoinService(db)
        self.notification_service = NotificationService(db)
        
    async def track_referral(
        self,
        referral_code: str,
        referred_user_id: str
    ) -> Dict[str, Any]:
        """Track a new referral"""
        # Find referrer
        referrer = await self.db.execute(
            select(User).where(User.referral_code == referral_code)
        )
        referrer = referrer.scalar()
        
        if not referrer:
            raise ValueError("Invalid referral code")
            
        if referrer.id == referred_user_id:
            raise ValueError("Cannot refer yourself")
            
        # Check if already tracked
        existing = await self.db.execute(
            select(ReferralTracking).where(
                ReferralTracking.referred_user_id == referred_user_id
            )
        )
        if existing.scalar():
            raise ValueError("User already referred")
            
        # Create tracking record
        tracking = ReferralTracking(
            referrer_id=referrer.id,
            referred_user_id=referred_user_id,
            referral_code_used=referral_code
        )
        
        self.db.add(tracking)
        
        # Award initial coins
        await self.coin_service.process_referral_reward(
            referrer_id=str(referrer.id),
            referred_id=referred_user_id
        )
        
        # Check milestones
        await self._check_milestones(referrer.id)
        
        # Send notifications
        await self.notification_service.create_notification(
            user_id=str(referrer.id),
            title="New Referral!",
            message=f"Someone joined using your referral code!",
            type="referral_success"
        )
        
        await self.db.commit()
        
        return {
            "referrer_name": referrer.name,
            "bonus_coins": 50
        }
        
    async def mark_referral_successful(
        self,
        referred_user_id: str,
        order_amount: float
    ):
        """Mark referral as successful after first purchase"""
        tracking = await self.db.execute(
            select(ReferralTracking).where(
                ReferralTracking.referred_user_id == referred_user_id
            )
        )
        tracking = tracking.scalar()
        
        if not tracking or tracking.has_made_purchase:
            return
            
        # Update tracking
        tracking.has_made_purchase = True
        tracking.first_purchase_date = datetime.utcnow()
        tracking.first_purchase_amount = order_amount
        
        # Calculate referrer reward (5% of order amount as coins)
        reward_amount = int(order_amount * 0.05)
        tracking.referrer_reward_amount = reward_amount
        
        # Award bonus coins to referrer
        await self.coin_service.award_coins(
            user_id=str(tracking.referrer_id),
            amount=reward_amount,
            reason="referral_purchase",
            description=f"Your referral made their first purchase!",
            reference_id=str(tracking.id)
        )
        
        await self.db.commit()
        
    async def get_user_referral_stats(self, user_id: str) -> Dict[str, Any]:
        """Get detailed referral statistics for user"""
        # Basic stats
        stats_query = """
        SELECT 
            COUNT(*) as total_referrals,
            COUNT(CASE WHEN has_made_purchase THEN 1 END) as successful_referrals,
            SUM(CASE WHEN has_made_purchase THEN referrer_reward_amount ELSE 0 END) as total_rewards,
            COUNT(CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 1 END) as monthly_referrals
        FROM referral_tracking
        WHERE referrer_id = %s
        """
        
        stats = await self.db.execute(stats_query, (user_id,))
        stats_data = stats.one()
        
        # Recent referrals
        recent_referrals = await self.db.execute(
            select(ReferralTracking)
            .options(selectinload(ReferralTracking.referred_user))
            .where(ReferralTracking.referrer_id == user_id)
            .order_by(ReferralTracking.created_at.desc())
            .limit(10)
        )
        
        # Get user's rank
        rank_query = """
        SELECT COUNT(DISTINCT referrer_id) + 1 as rank
        FROM referral_tracking
        WHERE referrer_id != %s
        GROUP BY referrer_id
        HAVING COUNT(*) > (
            SELECT COUNT(*) FROM referral_tracking WHERE referrer_id = %s
        )
        """
        
        rank_result = await self.db.execute(rank_query, (user_id, user_id))
        rank = rank_result.scalar() or 1
        
        return {
            "total_referrals": stats_data.total_referrals,
            "successful_referrals": stats_data.successful_referrals,
            "total_rewards": stats_data.total_rewards or 0,
            "monthly_referrals": stats_data.monthly_referrals,
            "global_rank": rank,
            "recent_referrals": [
                {
                    "user_name": ref.referred_user.name if ref.referred_user else "User",
                    "date": ref.created_at,
                    "has_purchased": ref.has_made_purchase
                }
                for ref in recent_referrals.scalars().all()
            ]
        }
        
    async def _check_milestones(self, user_id: uuid.UUID):
        """Check and award milestone rewards"""
        # Get user's referral count
        count = await self.db.scalar(
            select(func.count())
            .select_from(ReferralTracking)
            .where(ReferralTracking.referrer_id == user_id)
        )
        
        # Get unachieved milestones
        achieved_milestones = await self.db.execute(
            select(UserReferralMilestone.milestone_id)
            .where(UserReferralMilestone.user_id == user_id)
        )
        achieved_ids = [m for m in achieved_milestones.scalars().all()]
        
        # Check eligible milestones
        milestones = await self.db.execute(
            select(ReferralMilestone)
            .where(
                and_(
                    ReferralMilestone.required_referrals <= count,
                    ReferralMilestone.id.notin_(achieved_ids) if achieved_ids else True
                )
            )
        )
        
        for milestone in milestones.scalars().all():
            # Mark as achieved
            user_milestone = UserReferralMilestone(
                user_id=user_id,
                milestone_id=milestone.id,
                achieved_at=datetime.utcnow()
            )
            self.db.add(user_milestone)
            
            # Award reward
            if milestone.reward_type == "coins":
                await self.coin_service.award_coins(
                    user_id=str(user_id),
                    amount=milestone.reward_value,
                    reason="referral_milestone",
                    description=f"Achieved {milestone.name}",
                    reference_id=str(milestone.id)
                )
            elif milestone.reward_type == "badge" and milestone.badge_id:
                # Award badge
                from app.models import UserBadge
                user_badge = UserBadge(
                    user_id=user_id,
                    badge_id=milestone.badge_id,
                    assigned_by="system"
                )
                self.db.add(user_badge)
                
            # Send notification
            await self.notification_service.create_notification(
                user_id=str(user_id),
                title="Milestone Achieved!",
                message=f"Congratulations! You've achieved {milestone.name}",
                type="milestone_achieved",
                metadata={"milestone_id": str(milestone.id)}
            )
