# fastapi_cacheable/backend/base.py

"""
Abstract base class for cache backends.
Defines the interface that all cache backends must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

class BaseCacheBackend(ABC):
    """
    Abstract base class for cache backends.
    All cache backends must implement this interface.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from the cache by its key.
        
        :param key: The key to look up in the cache.
        :return: The cached value, or None if not found.
        """
        raise NotImplementedError
    
    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Set a value in the cache with an optional time-to-live (TTL).
        :param key: The key under which to store the value.
        :param value: The value to store in the cache.
        :param ttl: Optional time-to-live in seconds.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, key: str) -> None:
        """
        Delete a value from the cache by its key.
        :param key: The key to delete from the cache.
        """
        raise NotImplementedError

    @abstractmethod
    async def clear(self, namespace: Optional[str] = None) -> None:
        """
        Clear the cache, optionally within a specific namespace.
        :param namespace: Optional namespace to clear.
        """
        raise NotImplementedError