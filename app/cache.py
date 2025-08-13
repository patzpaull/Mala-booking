import json
import logging
from typing import Optional, Any
import asyncio

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)

class CacheService:
    _instance = None
    _redis_client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self._connect()
    
    def _connect(self):
        try:
            # Configure Redis connection
            try:
                from django.conf import settings
                redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            except ImportError:
                redis_url = 'redis://localhost:6379/0'
            self._redis_client = redis.from_url(
                redis_url,
                encoding='utf-8',
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            # Test connection
            self._redis_client.ping()
            logger.info("Redis connection established successfully")
        except redis.RedisError as e:
            logger.warning(f"Redis connection failed: {e}. Falling back to in-memory cache")
            self._redis_client = None
        except Exception as e:
            logger.warning(f"Unexpected error connecting to Redis: {e}. Falling back to in-memory cache")
            self._redis_client = None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if self._redis_client:
                value = await asyncio.get_event_loop().run_in_executor(
                    None, self._redis_client.get, key
                )
                if value:
                    return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL"""
        try:
            if self._redis_client:
                serialized_value = json.dumps(value, default=str)
                await asyncio.get_event_loop().run_in_executor(
                    None, self._redis_client.setex, key, ttl, serialized_value
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if self._redis_client:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._redis_client.delete, key
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> bool:
        """Clear all keys matching pattern"""
        try:
            if self._redis_client:
                keys = await asyncio.get_event_loop().run_in_executor(
                    None, self._redis_client.keys, pattern
                )
                if keys:
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._redis_client.delete, *keys
                    )
                return True
            return False
        except Exception as e:
            logger.error(f"Cache clear pattern error for {pattern}: {e}")
            return False

# Global cache instance
cache = CacheService()