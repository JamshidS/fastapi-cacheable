

class CacheError(RuntimeError):
	"""Base exception for cache-related errors."""


class CacheNotInitializedError(CacheError):
	"""Raised when cache decorators are used before CacheConfig.init()."""


__all__ = ["CacheError", "CacheNotInitializedError"]