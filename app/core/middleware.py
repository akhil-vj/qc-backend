"""
Application middleware for request/response processing
Handles CORS, rate limiting, logging, and error handling
"""

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import uuid
import logging
from typing import Callable
import json

from .config import settings
from .exceptions import QuickCartException, RateLimitException
from .cache import cache

logger = logging.getLogger(__name__)

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response

class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {request.client.host}"
        )
        
        try:
            response = await call_next(request)
            
            # Log response
            process_time = time.time() - start_time
            logger.info(
                f"Response: {response.status_code} "
                f"Time: {process_time:.3f}s "
                f"Request ID: {getattr(request.state, 'request_id', 'N/A')}"
            )
            
            # Add process time header
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {str(e)} "
                f"Time: {process_time:.3f}s"
            )
            raise

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware using Redis"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.rate_limits = {
            "/api/v1/auth/login": (5, 60),  # 5 requests per minute
            "/api/v1/auth/register": (3, 60),  # 3 requests per minute
            "/api/v1/auth/send-otp": (3, 300),  # 3 requests per 5 minutes
            "default": (100, 3600)  # 100 requests per hour
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        
        # Get client identifier (IP or user ID)
        client_id = request.client.host
        if hasattr(request.state, "user"):
            client_id = request.state.user.get("id", client_id)
        
        # Get rate limit for endpoint
        path = request.url.path
        limit, window = self.rate_limits.get(path, self.rate_limits["default"])
        
        # Create rate limit key
        key = f"rate_limit:{client_id}:{path}"
        
        # Check rate limit
        current_count = await cache.increment(key)
        if current_count == 1:
            # First request, set expiration
            await cache.redis_client.expire(key, window)
        
        if current_count > limit:
            # Get remaining time
            ttl = await cache.redis_client.ttl(key)
            raise RateLimitException(
                detail=f"Rate limit exceeded. Try again in {ttl} seconds.",
                retry_after=ttl
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current_count))
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + window)
        
        return response

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handler middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except QuickCartException as e:
            # Handle custom exceptions
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": {
                        "code": e.error_code,
                        "message": e.detail,
                        "request_id": getattr(request.state, "request_id", None)
                    }
                },
                headers=e.headers
            )
        except Exception as e:
            # Handle unexpected exceptions
            logger.exception(f"Unhandled exception: {str(e)}")
            
            # Don't expose internal errors in production
            if settings.DEBUG:
                detail = str(e)
            else:
                detail = "An unexpected error occurred"
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": detail,
                        "request_id": getattr(request.state, "request_id", None)
                    }
                }
            )

class CompressionMiddleware(BaseHTTPMiddleware):
    """Compress responses for better performance"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Only compress JSON responses
        if response.headers.get("content-type", "").startswith("application/json"):
            # Check if client accepts gzip
            accept_encoding = request.headers.get("accept-encoding", "")
            if "gzip" in accept_encoding:
                # Note: Actual compression would be handled by the server
                response.headers["Content-Encoding"] = "gzip"
        
        return response

def setup_middleware(app):
    """Configure all middleware for the application"""
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )
    
    # Add trusted host middleware for security
    if not settings.DEBUG:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*.quickcart.com", "quickcart.com"]
        )
    
    # Add custom middleware in order
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(CompressionMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
