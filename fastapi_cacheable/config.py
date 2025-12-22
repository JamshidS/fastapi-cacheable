# fastapi_cacheable/config.py

from typing import Optional

from fastapi_cacheable.backend.base import BaseCacheBackend
from fastapi_cacheable.serializer import (
    SerializationFormat,
    get_default_format,
    set_default_format,
)

class CacheConfigError(RuntimeError):
    """
    Raised when there is a configuration error in the cache setup.
    """


class CacheConfig:
    """
    Global cache configuration holder.

    This class manages the active cache backend and default
    serialization behavior used by cache decorators.
    """

    _backend: Optional[BaseCacheBackend] = None
    _initialized: bool = False

    @classmethod
    def init(
        cls,
        backend: BaseCacheBackend,
        *,
        default_serialization_format: Optional[SerializationFormat] = None,
    ) -> None:
        """
        Initialize the cache configuration.

        This MUST be called once at application startup.

        Args:
            backend: Cache backend implementation (e.g. RedisCacheBackend)
            default_serialization_format: Optional default serialization format

        Raises:
            CacheConfigError: If backend is invalid or config already initialized
        """
        if cls._initialized:
            raise CacheConfigError("CacheConfig is already initialized.")
        
        if not isinstance(backend, BaseCacheBackend):
            raise CacheConfigError(
                "Provided backend does not implement BaseCacheBackend."
            )
        
        cls._backend = backend
        if default_serialization_format is not None:
            set_default_format(default_serialization_format)
        cls._initialized = True

    @classmethod
    def is_initialized(cls) -> bool:
        """Check whether the cache configuration is initialized."""
        return cls._initialized
    
    @classmethod
    def get_backend(cls) -> BaseCacheBackend:
        """
        Get the configured cache backend.

        Raises:
            CacheConfigError: If config is not initialized

        Returns:
            Configured cache backend
        """
        if not cls._initialized or cls._backend is None:
            raise CacheConfigError(
                "CacheConfig is not initialized. Call CacheConfig.init() first."
            )
        return cls._backend
    
    
    @classmethod
    def reset(cls) -> None:
        """
        Reset cache configuration.

        Intended for testing ONLY.
        """
        cls._backend = None
        cls._initialized = False