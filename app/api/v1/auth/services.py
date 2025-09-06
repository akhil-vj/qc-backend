"""
Authentication service layer
Handles business logic for authentication
"""

from typing import Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import random
import string
import logging

from app.models import User, Reward
from app.core.security import SecurityUtils
from app.core.cache import cache
from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    UnauthorizedException,
    ConflictException,
    InvalidOTPException,
    InvalidReferralCodeException
)
from app.services.sms import SMSService
from app.services.email import EmailService
from .schemas import RegisterRequest, TokenResponse

logger = logging.getLogger(__name__)

class AuthService:
    """Authentication service"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.sms_service = SMSService()
        self.email_service = EmailService()
    
    async def send_otp(self, phone: str) -> dict:
        """
        Send OTP to phone number
        
        Args:
            phone: Phone number to send OTP to
            
        Returns:
            Dictionary with message and expiry time
        """
        # Generate OTP
        otp = SecurityUtils.generate_otp()
        
        # Store OTP in cache with expiry
        cache_key = f"otp:{phone}"
        expiry = settings.SMS_OTP_EXPIRY_MINUTES * 60
        
        await cache.set(cache_key, otp, expire=expiry)
        
        # Send SMS (in production and development with Twilio configured)
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            await self.sms_service.send_otp(phone, otp)
        else:
            # In development without Twilio, log OTP
            print(f"OTP for {phone}: {otp}")
            logger.info(f"OTP for {phone}: {otp}")
        
        return {
            "message": "OTP sent successfully",
            "expires_in": expiry
        }
    
    async def verify_otp(self, phone: str, otp: str) -> bool:
        """
        Verify OTP for phone number
        
        Args:
            phone: Phone number
            otp: OTP to verify
            
        Returns:
            True if OTP is valid
            
        Raises:
            InvalidOTPException: If OTP is invalid or expired
        """
        cache_key = f"otp:{phone}"
        stored_otp = await cache.get(cache_key)
        
        if not stored_otp:
            raise InvalidOTPException("OTP expired or not found")
        
        if stored_otp != otp:
            # Increment failed attempts
            attempts_key = f"otp_attempts:{phone}"
            attempts = await cache.increment(attempts_key)
            
            if attempts >= 3:
                # Block further attempts for some time
                await cache.delete(cache_key)
                await cache.set(f"otp_blocked:{phone}", "1", expire=3600)
                raise InvalidOTPException("Too many failed attempts. Please try again later.")
            
            raise InvalidOTPException("Invalid OTP")
        
        # OTP is valid, remove from cache
        await cache.delete(cache_key)
        await cache.delete(f"otp_attempts:{phone}")
        
        return True
    
    async def register(self, request: RegisterRequest) -> Tuple[User, bool]:
        """
        Register new user
        
        Args:
            request: Registration request data
            
        Returns:
            Tuple of (User, is_new_user)
            
        Raises:
            ConflictException: If phone/email already exists
            InvalidReferralCodeException: If referral code is invalid
        """
        # Check if user exists
        existing_user = await self.db.execute(
            select(User).where(User.phone == request.phone)
        )
        existing_user = existing_user.scalar_one_or_none()
        
        if existing_user:
            # User exists, return existing user
            return existing_user, False
        
        # Check email uniqueness if provided
        if request.email:
            email_exists = await self.db.execute(
                select(User).where(User.email == request.email)
            )
            if email_exists.scalar_one_or_none():
                raise ConflictException("User", "email", request.email)
        
        # Validate referral code if provided
        referred_by = None
        if request.referral_code:
            referrer = await self.db.execute(
                select(User).where(User.referral_code == request.referral_code)
            )
            referrer = referrer.scalar_one_or_none()
            
            if not referrer:
                raise InvalidReferralCodeException()
            
            referred_by = referrer.id
        
        # Create new user - all users start as regular users
        user = User(
            phone=request.phone,
            name=request.name,
            email=request.email,
            role="buyer",  # All users start as buyers, can upgrade to seller later
            referral_code=SecurityUtils.generate_referral_code(),
            referred_by_id=referred_by,
            is_verified=True,  # Phone verified via OTP
            last_login=datetime.now(timezone.utc)
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        return user, True
    
    async def login(self, phone: str) -> User:
        """
        Login user after OTP verification
        
        Args:
            phone: Verified phone number
            
        Returns:
            User object
            
        Raises:
            UnauthorizedException: If user not found
        """
        # Get user by phone
        result = await self.db.execute(
            select(User).where(
                and_(User.phone == phone, User.is_active == True)
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise UnauthorizedException("User not found or inactive")
        
        # Update last login
        user.last_login = datetime.utcnow()
        self.db.add(user)
        await self.db.commit()
        
        return user
    
    def generate_tokens(self, user: User) -> TokenResponse:
        """
        Generate access and refresh tokens for user
        
        Args:
            user: User object
            
        Returns:
            TokenResponse with tokens
        """
        # Token payload
        token_data = {
            "sub": str(user.id),
            "phone": user.phone,
            "email": user.email,
            "role": user.role,
            "is_verified": user.is_verified
        }
        
        # Generate tokens
        access_token = SecurityUtils.create_access_token(token_data)
        refresh_token = SecurityUtils.create_refresh_token(token_data)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: JWT refresh token
            
        Returns:
            New TokenResponse
            
        Raises:
            UnauthorizedException: If refresh token is invalid
        """
        try:
            # Decode refresh token
            payload = SecurityUtils.decode_token(refresh_token)
            
            if payload.get("type") != "refresh":
                raise UnauthorizedException("Invalid token type")
            
            # Get user
            user_id = payload.get("sub")
            result = await self.db.execute(
                select(User).where(
                    and_(User.id == user_id, User.is_active == True)
                )
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise UnauthorizedException("User not found or inactive")
            
            # Generate new tokens
            return self.generate_tokens(user)
            
        except Exception:
            raise UnauthorizedException("Invalid refresh token")
    
    async def change_role(self, user_id: str, new_role: str) -> User:
        """
        Change user role
        
        Args:
            user_id: User ID
            new_role: New role to assign
            
        Returns:
            Updated user object
        """
        # Get user
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise UnauthorizedException("User not found")
        
        # Update role
        user.role = new_role
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
