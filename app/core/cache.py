"""
Caching utilities for performance optimization.
This module provides caching functionality using Redis for expensive operations.
"""
import json
import pickle
from typing import Any, Optional, Union
from datetime import timedelta
import redis.asyncio as redis
from fastapi import Depends
from app.core.config import settings
from app.core.logging import logger

# Initialize Redis client with better error handling
# try:
#     # Only pass password if it's configured
#     redis_password = settings.redis.password_str if settings.redis.password_str else None
    
#     redis_client = redis.Redis(
#         host=settings.redis.host,
#         port=settings.redis.port,
#         db=settings.redis.db,
#         password=redis_password,  # Use None if no password is configured
#         decode_responses=False,
#         socket_connect_timeout=5,  # Add timeout for connection
#         socket_timeout=5
#     )
    
#     logger.info(f"Redis client initialized with host={settings.redis.host}, port={settings.redis.port}, db={settings.redis.db}")
#     logger.debug(f"Redis password configured: {'Yes' if redis_password else 'No'}")
    
# except Exception as e:
#     logger.error(f"Failed to initialize Redis client: {e}")
#     # Create a dummy client that will fail gracefully
#     redis_client = None

# Build connection kwargs without password if not set
redis_kwargs = {
    "host": settings.redis.host,
    "port": settings.redis.port,
    "db": settings.redis.db,
    "decode_responses": False,
    "socket_connect_timeout": 5,
    "socket_timeout": 5,
}

# Only include password if it's actually configured
if settings.redis.password_str:
    redis_kwargs["password"] = settings.redis.password_str

try:
    redis_client = redis.Redis(**redis_kwargs)
    logger.info(f"Redis client initialized: {settings.redis.host}:{settings.redis.port}, db={settings.redis.db}")
    logger.debug(f"Authentication: {'Enabled' if settings.redis.password_str else 'Disabled'}")
except Exception as e:
    logger.error(f"Failed to initialize Redis client: {e}")
    redis_client = None

async def get_cache() -> redis.Redis:
    """Get Redis client for caching."""
    if redis_client is None:
        logger.error("Redis client not initialized")
        raise RuntimeError("Redis client not initialized")
    return redis_client

async def set_cache(
    key: str,
    value: Any,
    expire: Optional[timedelta] = None,
    use_json: bool = True
) -> bool:
    """
    Set a value in cache.
    
    Args:
        key: Cache key
        value: Value to cache
        expire: Optional expiration time
        use_json: Whether to serialize as JSON (default) or pickle
        
    Returns:
        True if successful, False otherwise
    """
    if redis_client is None:
        logger.error("Cannot set cache: Redis client not initialized")
        return False
        
    try:
        if use_json:
            serialized_value = json.dumps(value, default=str)
        else:
            serialized_value = pickle.dumps(value)
        
        if expire:
            return await redis_client.setex(key, int(expire.total_seconds()), serialized_value)
        else:
            return await redis_client.set(key, serialized_value)
    except Exception as e:
        logger.error(f"Cache set error: {e}")
        return False

async def get_cache(
    key: str,
    use_json: bool = True
) -> Optional[Any]:
    """
    Get a value from cache.
    
    Args:
        key: Cache key
        use_json: Whether to deserialize from JSON (default) or pickle
        
    Returns:
        Cached value or None if not found
    """
    if redis_client is None:
        logger.error("Cannot get cache: Redis client not initialized")
        return None
        
    try:
        value = await redis_client.get(key)
        if value is None:
            return None
        
        if use_json:
            return json.loads(value)
        else:
            return pickle.loads(value)
    except Exception as e:
        logger.error(f"Cache get error: {e}")
        return None

async def delete_cache(key: str) -> bool:
    """
    Delete a value from cache.
    
    Args:
        key: Cache key
        
    Returns:
        True if successful, False otherwise
    """
    if redis_client is None:
        logger.error("Cannot delete cache: Redis client not initialized")
        return False
        
    try:
        return await redis_client.delete(key)
    except Exception as e:
        logger.error(f"Cache delete error: {e}")
        return False

async def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalidate all cache keys matching a pattern.
    
    Args:
        pattern: Cache key pattern (e.g., "report:*")
        
    Returns:
        Number of keys deleted
    """
    if redis_client is None:
        logger.error("Cannot invalidate cache: Redis client not initialized")
        return 0
        
    try:
        keys = []
        async for key in redis_client.scan_iter(match=pattern):
            keys.append(key)
        
        if keys:
            return await redis_client.delete(*keys)
        return 0
    except Exception as e:
        logger.error(f"Cache invalidate pattern error: {e}")
        return 0

# Additional utility functions
async def check_redis_connection() -> bool:
    """Check if Redis connection is working."""
    if redis_client is None:
        return False
        
    try:
        return await redis_client.ping()
    except Exception as e:
        logger.error(f"Redis connection check failed: {e}")
        return False

# Cache key prefix to avoid collisions
CACHE_PREFIX = "ufm:"

def get_cache_key(key: str) -> str:
    """Get prefixed cache key."""
    return f"{CACHE_PREFIX}{key}"

# Helper function to resolve the overloaded get_cache function
async def get_cache_value(key: str, use_json: bool = True) -> Optional[Any]:
    """Helper function to get cache values (resolves name conflict)."""
    return await get_cache(key, use_json)
