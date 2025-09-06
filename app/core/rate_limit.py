"""Enhanced rate limiting with Redis"""

from typing import Optional, Callable
from datetime import datetime, timedelta
import hashlib
from functools import wraps

from fastapi import HTTPException, Request
from app.core.cache import cache
from app.core.config import settings

class RateLimiter:
    """Advanced rate limiting implementation"""
    
    def __init__(
        self,
        calls: int,
        period: timedelta,
        identifier: Optional[Callable] = None,
        scope: str = "global"
    ):
        self.calls = calls
        self.period = period
        self.identifier = identifier or self._default_identifier
        self.scope = scope
        
    def _default_identifier(self, request: Request) -> str:
        """Default identifier using IP address"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0]
        else:
            ip = request.client.host
        return ip
        
    async def check_rate_limit(self, request: Request) -> bool:
        """Check if request is within rate limit"""
        identifier = self.identifier(request)
        key = f"rate_limit:{self.scope}:{identifier}"
        
        # Get current count
        current = await cache.get(key)
        
        if current is None:
            # First request
            await cache.set(key, 1, expire=self.period)
            return True
            
        if current >= self.calls:
            # Rate limit exceeded
            return False
            
        # Increment counter
        await cache.increment(key)
        return True
        
    def __call__(self, func):
        """Decorator for rate limiting"""
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            if not await self.check_rate_limit(request):
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(self.period.total_seconds())}
                )
            return await func(request, *args, **kwargs)
        return wrapper

class IPBlacklist:
    """IP blacklisting system"""
    
    @staticmethod
    async def add_ip(ip: str, reason: str, duration: Optional[timedelta] = None):
        """Add IP to blacklist"""
        key = f"blacklist:ip:{ip}"
        value = {
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
            "permanent": duration is None
        }
        
        if duration:
            await cache.set(key, value, expire=duration)
        else:
            await cache.set(key, value)
            
    @staticmethod
    async def remove_ip(ip: str):
        """Remove IP from blacklist"""
        await cache.delete(f"blacklist:ip:{ip}")
        
    @staticmethod
    async def is_blacklisted(ip: str) -> bool:
        """Check if IP is blacklisted"""
        return await cache.exists(f"blacklist:ip:{ip}")
        
class SecurityMiddleware:
    """Enhanced security middleware"""
    
    async def __call__(self, request: Request, call_next):
        # Check IP blacklist
        client_ip = request.client.host
        if await IPBlacklist.is_blacklisted(client_ip):
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Add security headers
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response
