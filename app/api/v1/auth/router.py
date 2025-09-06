"""
Authentication API routes
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.exceptions import BadRequestException
from .schemas import (
    SendOTPRequest,
    VerifyOTPRequest,
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    ChangeRoleRequest,
    OTPResponse,
    AuthResponse,
    UserResponse,
    TokenResponse
)
from .services import AuthService

router = APIRouter()

@router.post(
    "/send-otp",
    response_model=OTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Send OTP to phone number",
    description="Send a one-time password to the provided phone number for verification"
)
async def send_otp(
    request: SendOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send OTP for phone verification"""
    service = AuthService(db)
    result = await service.send_otp(request.phone)
    return OTPResponse(**result)

@router.post(
    "/verify-otp",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP",
    description="Verify the OTP sent to the phone number"
)
async def verify_otp(
    request: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify OTP without login"""
    service = AuthService(db)
    await service.verify_otp(request.phone, request.otp)
    return {"message": "OTP verified successfully"}

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Register a new user account with verified phone number"
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register new user after OTP verification"""
    service = AuthService(db)
    
    # Note: In production, verify OTP was completed before registration
    # This could be done with a temporary token after OTP verification
    
    user, is_new = await service.register(request)
    tokens = service.generate_tokens(user)
    
    return AuthResponse(
        user=UserResponse.from_orm(user),
        tokens=tokens,
        is_new_user=is_new
    )

@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Login user",
    description="Login with phone number and OTP"
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login user with OTP"""
    service = AuthService(db)
    
    # Verify OTP
    await service.verify_otp(request.phone, request.otp)
    
    # Login user
    user = await service.login(request.phone)
    tokens = service.generate_tokens(user)
    
    return AuthResponse(
        user=UserResponse.from_orm(user),
        tokens=tokens,
        is_new_user=False
    )

@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Get new access token using refresh token"
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token"""
    service = AuthService(db)
    tokens = await service.refresh_tokens(request.refresh_token)
    return tokens

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout user",
    description="Logout current user and invalidate tokens"
)
async def logout(
    current_user: dict = Depends(get_current_user)
):
    """
    Logout user
    Note: In production, you might want to blacklist the token
    """
    # Token blacklisting can be implemented here
    return None

@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Get currently authenticated user information"
)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user information"""
    from app.models import User
    from sqlalchemy import select
    
    result = await db.execute(
        select(User).where(User.id == current_user["id"])
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise BadRequestException("User not found")
    
    return UserResponse.from_orm(user)

@router.put(
    "/change-role",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Change user role",
    description="Switch between buyer and seller roles"
)
async def change_role(
    request: ChangeRoleRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user role"""
    service = AuthService(db)
    user = await service.change_role(current_user["id"], request.new_role)
    return UserResponse.from_orm(user)
