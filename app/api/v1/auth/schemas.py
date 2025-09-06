"""
Authentication schemas for request/response validation
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
import re

def validate_phone_number(v: str) -> str:
    """Validate and normalize phone number"""
    if not v:
        raise ValueError("Phone number is required")
    
    # Remove spaces and special characters
    v = re.sub(r'[^\d+]', '', v)
    
    # Indian phone number validation
    if not re.match(r'^(\+91)?[6-9]\d{9}$', v):
        raise ValueError("Invalid Indian phone number")
    
    # Normalize to +91 format
    if not v.startswith('+91'):
        v = '+91' + v[-10:]
    
    return v

class SendOTPRequest(BaseModel):
    """Request to send OTP"""
    phone: str = Field(..., description="Phone number with or without +91 prefix", examples=["9876543210", "+919876543210"])
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        return validate_phone_number(v)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "phone": "9876543210"
            }
        }
    }

class VerifyOTPRequest(BaseModel):
    """Request to verify OTP"""
    phone: str = Field(..., description="Phone number with or without +91 prefix", examples=["9876543210", "+919876543210"])
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP", examples=["123456"])
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        return validate_phone_number(v)
    
    @field_validator('otp')
    @classmethod
    def validate_otp(cls, v):
        if not re.match(r'^[0-9]{6}$', v):
            raise ValueError("OTP must be exactly 6 digits")
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "phone": "9876543210",
                "otp": "123456"
            }
        }
    }

class RegisterRequest(BaseModel):
    """User registration request"""
    phone: str = Field(..., description="Phone number with or without +91 prefix", examples=["9876543210", "+919876543210"])
    name: str = Field(..., min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    referral_code: Optional[str] = Field(None, min_length=6, max_length=10)
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        return validate_phone_number(v)
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not re.match(r'^[a-zA-Z\s]+$', v):
            raise ValueError("Name should only contain letters and spaces")
        return v.strip()
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "phone": "9876543210",
                "name": "John Doe",
                "email": "john@example.com",
                "referral_code": "ABC123"
            }
        }
    }

class LoginRequest(BaseModel):
    """User login request"""
    phone: str = Field(..., description="Phone number with or without +91 prefix", examples=["9876543210", "+919876543210"])
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP", examples=["123456"])
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        return validate_phone_number(v)
    
    @field_validator('otp')
    @classmethod
    def validate_otp(cls, v):
        if not re.match(r'^[0-9]{6}$', v):
            raise ValueError("OTP must be exactly 6 digits")
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "phone": "9876543210",
                "otp": "123456"
            }
        }
    }

class RefreshTokenRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str = Field(..., description="JWT refresh token")

class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiry in seconds")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }
    }

class UserResponse(BaseModel):
    """User information response"""
    id: str
    phone: str
    name: Optional[str]
    email: Optional[str]
    role: str
    is_verified: bool
    trust_score: int
    referral_code: str
    profile_image: Optional[str]
    created_at: datetime
    
    model_config = {
        "from_attributes": True
    }

class AuthResponse(BaseModel):
    """Authentication response with tokens and user info"""
    user: UserResponse
    tokens: TokenResponse
    is_new_user: bool = False
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "phone": "+919876543210",
                    "name": "John Doe",
                    "email": "john@example.com",
                    "role": "buyer",
                    "is_verified": True,
                    "trust_score": 50,
                    "referral_code": "JOHN123",
                    "profile_image": None,
                    "created_at": "2024-01-01T00:00:00Z"
                },
                "tokens": {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 1800
                },
                "is_new_user": False
            }
        }
    }

class ChangeRoleRequest(BaseModel):
    """Request to change user role"""
    new_role: str = Field(..., pattern="^(buyer|seller)$")

class OTPResponse(BaseModel):
    """OTP send response"""
    message: str
    expires_in: int = Field(..., description="OTP expiry in seconds")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "OTP sent successfully",
                "expires_in": 300
            }
        }
    }
