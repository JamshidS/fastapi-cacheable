# fastapi_cacheable/backend/redis.py

from typing import Any, Optional

import redis.asyncio as redis

from .base import BaseCacheBackend
from fastapi_cacheable.serializer import serialize, deserialize


class RedisCacheBackend(BaseCacheBackend):
    """
    Redis cache backend implementation.
    Uses redis-py for asynchronous Redis operations.
    """

    def __init__(
        self,
        client: redis.Redis,
        key_prefix: str = "fastapi-cacheable",
    ) -> None:
        self.client = client
        self.key_prefix = key_prefix

    def _builld_key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        redis_key = self._builld_key(key)
        raw =  await self.client.get(redis_key)

        if raw is None:
            return None
        
        return deserialize(raw)
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = 3600,
    ) -> None:
        redis_key = self._builld_key(key)
        data = serialize(value)

        await self.client.set(name=redis_key, value=data, ex=ttl)

    async def delete(self, key: str) -> None:
        redis_key = self._builld_key(key)
        await self.client.delete(redis_key)

    async def clear(self, namespace: Optional[str] = None) -> None:
        """
        Clear cache keys.
        WARNING: Uses KEYS command (acceptable for explicit eviction).
        """
        pattern = (
            f"{self.key_prefix}:{namespace}:*"
            if namespace
            else f"{self.key_prefix}:*"
        )

        keys = await self.client.keys(pattern)
        if keys:
            await self.client.delete(*keys)