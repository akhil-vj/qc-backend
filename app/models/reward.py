"""
Rewards and gamification models
"""

from sqlalchemy import Column, String, Integer, Date, ForeignKey, Index, UniqueConstraint, CheckConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from .base import Base, TimestampedModel

class Reward(Base, TimestampedModel):
    """User rewards and loyalty program"""
    
    __tablename__ = "rewards"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    
    # Coins
    coins = Column(Integer, default=0)
    lifetime_coins = Column(Integer, default=0)
    
    # Streaks
    streak_days = Column(Integer, default=0)
    last_checkin = Column(Date, nullable=True)
    
    # Referrals
    referral_count = Column(Integer, default=0)
    
    # Tier system
    tier = Column(String(50), default="bronze")  # bronze, silver, gold, platinum
    tier_progress = Column(Integer, default=0)
    
    # Achievements
    achievements = Column(JSONB, default=[])
    
    # Statistics
    total_savings = Column(Numeric(10, 2), default=0)
    orders_count = Column(Integer, default=0)
    
    # Relationships
    user = relationship("User", back_populates="reward")
    transactions = relationship("RewardTransaction", back_populates="reward")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("coins >= 0", name="check_non_negative_coins"),
        CheckConstraint("streak_days >= 0", name="check_non_negative_streak"),
        Index("idx_rewards_tier", "tier"),
    )

class RewardTransaction(Base, TimestampedModel):
    """Reward transaction history"""
    
    __tablename__ = "reward_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reward_id = Column(UUID(as_uuid=True), ForeignKey("rewards.id"), nullable=False)
    
    # Transaction details
    type = Column(String(50), nullable=False)  # earned, redeemed, expired, adjusted
    coins = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    
    # Reference
    reference_type = Column(String(50), nullable=True)  # order, referral, checkin, etc.
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    
    description = Column(String(500), nullable=False)
    
    # Relationships
    reward = relationship("Reward", back_populates="transactions")
    
    # Indexes
    __table_args__ = (
        Index("idx_reward_transactions_reward_type", "reward_id", "type"),
        Index("idx_reward_transactions_created", "created_at"),
    )
