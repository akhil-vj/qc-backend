"""Rate limiting middleware using slowapi"""

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import redis.asyncio as redis
from typing import Optional, Callable
import hashlib
import json

from app.core.config import settings

# Custom key function that considers user authentication
def get_rate_limit_key(request: Request) -> str:
    """Get rate limit key based on user or IP"""
    # Try to get user ID from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)
    
    if user_id:
        return f"user:{user_id}"
    
    # Fall back to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0]
    else:
        ip = request.client.host
        
    return f"ip:{ip}"

# Create limiter instance
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["1000 per hour"],
    storage_uri=settings.REDIS_URL,
    strategy="fixed-window",
    headers_enabled=True
)

# Custom rate limit exceeded handler
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    response = JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": f"Too many requests. {exc.detail}"
        }
    )
    response = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
    return response

# Rate limiting decorators for different endpoints
auth_limiter = limiter.shared_limit("5/minute", scope="auth")
search_limiter = limiter.shared_limit("30/minute", scope="search")
api_limiter = limiter.shared_limit("100/minute", scope="api")
anonymous_limiter = limiter.shared_limit("20/minute", scope="anonymous")

# Custom rate limiter for specific use cases
class CustomRateLimiter:
    """Custom rate limiter with Redis backend"""
    
    def __init__(self):
        self.redis_client = None
        
    async def init(self):
        """Initialize Redis connection"""
        self.redis_client = await redis.from_url(settings.REDIS_URL)
        
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int,
        cost: int = 1
    ) -> tuple[bool, dict]:
        """Check if request is within rate limit"""
        if not self.redis_client:
            await self.init()
            
        # Use sliding window algorithm
        now = int(datetime.utcnow().timestamp())
        window_start = now - window
        
        pipe = self.redis_client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count requests in window
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {f"{now}:{hash(str(now))}": now})
        
        # Set expiry
        pipe.expire(key, window)
        
        results = await pipe.execute()
        
        current_requests = results[1]
        
        if current_requests + cost > limit:
            return False, {
                "limit": limit,
                "remaining": max(0, limit - current_requests),
                "reset": now + window
            }
            
        return True, {
            "limit": limit,
            "remaining": limit - current_requests - cost,
            "reset": now + window
        }

# Decorator for custom rate limiting
def rate_limit(
    limit: int,
    window: int = 60,
    scope: str = "default",
    cost: int = 1
):
    """Custom rate limit decorator"""
    def decorator(func: Callable) -> Callable:
        async def wrapper(request: Request, *args, **kwargs):
            limiter = CustomRateLimiter()
            
            # Get rate limit key
            key_parts = [scope]
            
            # Add user ID if authenticated
            if hasattr(request.state, "user_id"):
                key_parts.append(f"user:{request.state.user_id}")
            else:
                # Use IP address
                ip = get_remote_address(request)
                key_parts.append(f"ip:{ip}")
                
            key = ":".join(key_parts)
            
            # Check rate limit
            allowed, headers = await limiter.check_rate_limit(key, limit, window, cost)
            
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit": str(headers["limit"]),
                        "X-RateLimit-Remaining": str(headers["remaining"]),
                        "X-RateLimit-Reset": str(headers["reset"]),
                        "Retry-After": str(headers["reset"] - int(datetime.utcnow().timestamp()))
                    }
                )
                
            # Call the actual function
            response = await func(request, *args, **kwargs)
            
            # Add rate limit headers to response
            if isinstance(response, Response):
                response.headers["X-RateLimit-Limit"] = str(headers["limit"])
                response.headers["X-RateLimit-Remaining"] = str(headers["remaining"])
                response.headers["X-RateLimit-Reset"] = str(headers["reset"])
                
            return response
            
        return wrapper
    return decorator
