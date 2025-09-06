"""
User model and related schemas
Handles user authentication and profile information
"""

from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Index, UniqueConstraint, DateTime, Date, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB, JSON
from sqlalchemy.orm import relationship
import uuid
import enum

from .base import Base, TimestampedModel, UUIDModel, SoftDeleteModel

class UserRole(str, enum.Enum):
    BUYER = "buyer"
    SELLER = "seller"
    ADMIN = "admin"
    SUPPORT = "support"

class User(Base, TimestampedModel, UUIDModel, SoftDeleteModel):
    """User model with all mixins"""
    
    __tablename__ = "users"
    
    # User fields
    phone = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, index=True)
    name = Column(String(100), nullable=False)
    password_hash = Column(String(255))
    role = Column(Enum(UserRole), default=UserRole.BUYER, nullable=False)
    
    # Profile fields
    profile_image = Column(String(500), nullable=True)  # keeping original name for compatibility
    bio = Column(String(500))
    date_of_birth = Column(DateTime(timezone=True))
    
    # Status fields
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    banned_at = Column(DateTime(timezone=True))
    ban_reason = Column(String(500))
    
    # Verification fields
    phone_verified = Column(Boolean, default=False, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime(timezone=True))
    
    # Two-factor auth
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_secret = Column(String(100))
    two_factor_backup_codes = Column(JSON)
    
    # Coins and rewards
    coin_balance = Column(Integer, default=0, nullable=False)
    total_coins_earned = Column(Integer, default=0, nullable=False)
    total_coins_spent = Column(Integer, default=0, nullable=False)
    
    # Trust score (keeping from original)
    trust_score = Column(Integer, default=50)
    
    # Referral
    referral_code = Column(String(20), unique=True, index=True)
    referred_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # keeping original name
    referral_count = Column(Integer, default=0)
    
    # Settings and preferences
    notification_preferences = Column(JSON, default={})
    privacy_settings = Column(JSON, default={})
    language = Column(String(5), default="en")
    timezone = Column(String(50), default="UTC")
    
    # User metadata (renamed from metadata to avoid SQLAlchemy conflict)
    user_metadata = Column(JSONB, default={})
    
    # Analytics
    last_login = Column(DateTime(timezone=True), nullable=True)  # keeping original name
    last_active_at = Column(DateTime(timezone=True))
    login_count = Column(Integer, default=0)
    
    # Relationships
    referred_by = relationship("User", remote_side="User.id", backref="referrals")
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    products = relationship("Product", back_populates="seller")
    orders_as_buyer = relationship(
        "Order",
        foreign_keys="Order.buyer_id",
        back_populates="buyer"
    )
    orders_as_seller = relationship(
        "Order",
        foreign_keys="Order.seller_id",
        back_populates="seller"
    )
    reviews = relationship("Review", back_populates="user", cascade="all, delete-orphan")
    addresses = relationship("Address", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user")
    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    wishlist_items = relationship("WishlistItem", back_populates="user")
    reward = relationship("Reward", back_populates="user", uselist=False)
    seller_profile = relationship("SellerProfile", back_populates="user", uselist=False)
    coin_transactions = relationship("CoinTransaction", back_populates="user")
    coin_redemptions = relationship("CoinRedemption", back_populates="user")
    referral_tracking_made = relationship(
        "ReferralTracking",
        foreign_keys="ReferralTracking.referrer_id",
        back_populates="referrer"
    )
    referral_tracking_received = relationship(
        "ReferralTracking",
        foreign_keys="ReferralTracking.referred_user_id",
        back_populates="referred_user",
        uselist=False
    )
    device_tokens = relationship("DeviceToken", back_populates="user")
    
    # Indexes
    __table_args__ = (
        Index("idx_users_role_active", "role", "is_active"),
        Index("idx_users_referral_code", "referral_code"),
        Index("idx_users_created_role", "created_at", "role"),
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.referral_code:
            self.generate_referral_code()
            
    def generate_referral_code(self):
        """Generate unique referral code"""
        import random
        import string
        
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            # Check uniqueness in service layer
            self.referral_code = code
            break
    
    def __repr__(self):
        return f"<User {self.name or self.phone}>"

class UserProfile(Base, TimestampedModel, UUIDModel):
    """Extended user profile information"""
    
    __tablename__ = "user_profiles"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)
    bio = Column(Text, nullable=True)
    preferences = Column(JSONB, default={})
    notification_settings = Column(JSONB, default={
        "email": True,
        "sms": True,
        "push": True,
        "order_updates": True,
        "promotions": True,
        "price_alerts": True
    })
    privacy_settings = Column(JSONB, default={
        "profile_visible": True,
        "show_purchases": False,
        "allow_reviews": True
    })
    
    # Relationships
    user = relationship("User", back_populates="profile")
