"""
Custom exception classes and error handlers
Provides consistent error responses across the application
"""

from fastapi import HTTPException, status
from typing import Any, Dict, Optional

class QuickCartException(HTTPException):
    """Base exception class for QuickCart application"""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code

class BadRequestException(QuickCartException):
    """400 Bad Request"""
    
    def __init__(self, detail: str, error_code: str = "BAD_REQUEST"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code=error_code
        )

class UnauthorizedException(QuickCartException):
    """401 Unauthorized"""
    
    def __init__(self, detail: str = "Unauthorized", error_code: str = "UNAUTHORIZED"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code=error_code,
            headers={"WWW-Authenticate": "Bearer"}
        )

class ForbiddenException(QuickCartException):
    """403 Forbidden"""
    
    def __init__(self, detail: str = "Forbidden", error_code: str = "FORBIDDEN"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code=error_code
        )

class NotFoundException(QuickCartException):
    """404 Not Found"""
    
    def __init__(self, detail: str = "Not found", error_code: str = "NOT_FOUND"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            error_code=error_code
        )

class ConflictException(QuickCartException):
    """409 Conflict"""
    
    def __init__(self, detail: str, error_code: str = "CONFLICT"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code=error_code
        )

class ValidationException(QuickCartException):
    """422 Unprocessable Entity"""
    
    def __init__(self, detail: str, error_code: str = "VALIDATION_ERROR"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code=error_code
        )

class RateLimitException(QuickCartException):
    """429 Too Many Requests"""
    
    def __init__(
        self, 
        detail: str = "Rate limit exceeded", 
        error_code: str = "RATE_LIMIT_EXCEEDED",
        retry_after: Optional[int] = None
    ):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            error_code=error_code,
            headers=headers
        )

class InternalServerException(QuickCartException):
    """500 Internal Server Error"""
    
    def __init__(
        self, 
        detail: str = "Internal server error", 
        error_code: str = "INTERNAL_ERROR"
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code=error_code
        )

class ServiceUnavailableException(QuickCartException):
    """503 Service Unavailable"""
    
    def __init__(
        self, 
        detail: str = "Service temporarily unavailable", 
        error_code: str = "SERVICE_UNAVAILABLE"
    ):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code=error_code
        )

# Business logic exceptions
class InsufficientStockException(BadRequestException):
    """Product stock insufficient"""
    
    def __init__(self, product_name: str, available: int):
        super().__init__(
            detail=f"Insufficient stock for {product_name}. Only {available} available.",
            error_code="INSUFFICIENT_STOCK"
        )

class InvalidPaymentException(BadRequestException):
    """Payment validation failed"""
    
    def __init__(self, detail: str):
        super().__init__(
            detail=detail,
            error_code="INVALID_PAYMENT"
        )

class InvalidOTPException(BadRequestException):
    """OTP validation failed"""
    
    def __init__(self, detail: str = "Invalid or expired OTP"):
        super().__init__(
            detail=detail,
            error_code="INVALID_OTP"
        )

class DuplicateResourceException(ConflictException):
    """Resource already exists"""
    
    def __init__(self, resource: str, field: str, value: str):
        super().__init__(
            detail=f"{resource} with {field} '{value}' already exists",
            error_code="DUPLICATE_RESOURCE"
        )

class InvalidReferralCodeException(BadRequestException):
    """Referral code validation failed"""
    
    def __init__(self, detail: str = "Invalid referral code"):
        super().__init__(
            detail=detail,
            error_code="INVALID_REFERRAL_CODE"
        )

class OrderNotCancellableException(BadRequestException):
    """Order cannot be cancelled"""
    
    def __init__(self, detail: str = "Order cannot be cancelled in current status"):
        super().__init__(
            detail=detail,
            error_code="ORDER_NOT_CANCELLABLE"
        )
