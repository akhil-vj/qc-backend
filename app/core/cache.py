"""
Redis cache configuration and utilities
Provides caching decorators and cache management functions
"""

import redis.asyncio as redis
from typing import Optional, Any, Union, Callable
from functools import wraps
import json
import pickle
import asyncio
from datetime import timedelta, datetime
import logging

from .config import settings

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis cache manager with in-memory fallback"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._fallback_cache: dict = {}  # In-memory fallback for development
        self._use_redis = True
        
    async def connect(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=settings.REDIS_DECODE_RESPONSES,
                max_connections=settings.REDIS_MAX_CONNECTIONS
            )
            await self.redis_client.ping()
            logger.info("Redis connection established")
            self._use_redis = True
        except Exception as e:
            logger.warning(f"Failed to connect to Redis, using in-memory fallback: {e}")
            self._use_redis = False
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if self._use_redis and self.redis_client:
                value = await self.redis_client.get(key)
                if value:
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        return pickle.loads(value.encode('latin-1'))
                return None
            else:
                # Use in-memory fallback
                cache_item = self._fallback_cache.get(key)
                if cache_item:
                    # Check expiry
                    if cache_item.get('expires_at'):
                        if datetime.now() > cache_item['expires_at']:
                            del self._fallback_cache[key]
                            return None
                    return cache_item['value']
                return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set value in cache with optional expiration"""
        try:
            if self._use_redis and self.redis_client:
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                else:
                    value = pickle.dumps(value).decode('latin-1')
                
                if expire:
                    if isinstance(expire, timedelta):
                        expire = int(expire.total_seconds())
                    return await self.redis_client.setex(key, expire, value)
                else:
                    return await self.redis_client.set(key, value)
            else:
                # Use in-memory fallback
                cache_item = {'value': value}
                if expire:
                    if isinstance(expire, timedelta):
                        expire = int(expire.total_seconds())
                    cache_item['expires_at'] = datetime.now() + timedelta(seconds=expire)
                self._fallback_cache[key] = cache_item
                return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if self._use_redis and self.redis_client:
                return bool(await self.redis_client.delete(key))
            else:
                # Use in-memory fallback
                if key in self._fallback_cache:
                    del self._fallback_cache[key]
                    return True
                return False
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            if self._use_redis and self.redis_client:
                return bool(await self.redis_client.exists(key))
            else:
                # Use in-memory fallback
                cache_item = self._fallback_cache.get(key)
                if cache_item:
                    # Check expiry
                    if cache_item.get('expires_at'):
                        if datetime.now() > cache_item['expires_at']:
                            del self._fallback_cache[key]
                            return False
                    return True
                return False
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter value"""
        try:
            if self._use_redis and self.redis_client:
                return await self.redis_client.incr(key, amount)
            else:
                # Use in-memory fallback
                cache_item = self._fallback_cache.get(key, {'value': 0})
                cache_item['value'] = cache_item.get('value', 0) + amount
                self._fallback_cache[key] = cache_item
                return cache_item['value']
        except Exception as e:
            logger.error(f"Cache increment error: {e}")
            return 0
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error: {e}")
            return 0
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter in cache"""
        try:
            return await self.redis_client.incr(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error: {e}")
            return None
    
    async def decrement(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement counter in cache"""
        try:
            return await self.redis_client.decr(key, amount)
        except Exception as e:
            logger.error(f"Cache decrement error: {e}")
            return None

# Global cache instance
cache = RedisCache()

def cached(
    key_prefix: str,
    expire: Optional[Union[int, timedelta]] = 3600,
    key_func: Optional[Callable] = None
):
    """
    Decorator for caching function results
    
    Args:
        key_prefix: Prefix for cache key
        expire: Expiration time in seconds or timedelta
        key_func: Function to generate cache key from arguments
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = f"{key_prefix}:{key_func(*args, **kwargs)}"
            else:
                # Simple key generation from args
                key_parts = [str(arg) for arg in args]
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = f"{key_prefix}:{':'.join(key_parts)}"
            
            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, expire)
            
            return result
        return wrapper
    return decorator

def invalidate_cache(pattern: str):
    """
    Decorator to invalidate cache matching pattern after function execution
    
    Args:
        pattern: Cache key pattern to delete (supports wildcards)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            await cache.delete_pattern(pattern)
            return result
        return wrapper
    return decorator
