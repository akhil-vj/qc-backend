# Backend Security Configuration
# Security headers, CORS, rate limiting, and other security measures

import os
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import redis.asyncio as redis

# Initialize rate limiter
def create_limiter():
    """Create rate limiter with Redis backend"""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return Limiter(
        key_func=get_remote_address,
        storage_uri=redis_url,
        default_limits=["1000/hour"]
    )

def setup_security_middleware(app: FastAPI) -> None:
    """Configure all security middleware for the FastAPI application"""
    
    # Rate limiting
    limiter = create_limiter()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # CORS Configuration
    cors_origins = os.getenv("CORS_ORIGINS", "[]")
    if isinstance(cors_origins, str):
        import json
        try:
            cors_origins = json.loads(cors_origins)
        except json.JSONDecodeError:
            cors_origins = ["http://localhost:3000"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-CSRF-Token",
            "Cache-Control",
        ],
        expose_headers=["X-Total-Count", "X-Page-Count"],
    )
    
    # Trusted Host Middleware
    allowed_hosts = os.getenv("ALLOWED_HOSTS", "[]")
    if isinstance(allowed_hosts, str):
        import json
        try:
            allowed_hosts = json.loads(allowed_hosts)
        except json.JSONDecodeError:
            allowed_hosts = ["localhost", "127.0.0.1"]
    
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=allowed_hosts
    )

def setup_security_headers(app: FastAPI) -> None:
    """Add security headers to all responses"""
    
    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        
        # Content Security Policy
        if os.getenv("ENVIRONMENT") == "production":
            csp = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' fonts.googleapis.com; font-src 'self' fonts.gstatic.com; img-src 'self' data: blob: res.cloudinary.com; connect-src 'self'"
            response.headers["Content-Security-Policy"] = csp
        
        # HSTS (only in production with HTTPS)
        if os.getenv("HTTPS_ENABLED") == "True":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response

# Rate limiting decorators for different endpoint types
def auth_rate_limit():
    """Rate limit for authentication endpoints"""
    return os.getenv("RATE_LIMIT_AUTH", "5/minute")

def api_rate_limit():
    """Rate limit for general API endpoints"""
    return os.getenv("RATE_LIMIT_DEFAULT", "100/hour")

def upload_rate_limit():
    """Rate limit for file upload endpoints"""
    return "10/minute"

def webhook_rate_limit():
    """Rate limit for webhook endpoints"""
    return "1000/hour"
