# fastapi_cacheable/key_builder.py

from __future__ import annotations

import hashlib
import inspect
import json
from datetime import datetime, date, time
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional, Protocol
from uuid import UUID


class KeyBuilder(Protocol):
    """
    Interface for cache key builders.
    """

    def build(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> str:
        """
        Build a cache key based on the function and its arguments.

        :param func: The target function being cached.
        :param args: Positional arguments passed to the function.
        :param kwargs: Keyword arguments passed to the function.
        :return: A string representing the cache key.
        """
        ...


class DefaultKeyBuilder:
    """
    Default implementation of KeyBuilder.
    Constructs a cache key using the function's module, name,
    and a hash of its arguments.
    """

    def __init__(self, prefix: Optional[str] = None) -> None:
        self.prefix = prefix or "fastapi-cacheable"

    def build(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> str:  
        """
        Build a cache key based on the function and its arguments.
        :param func: The target function being cached.
        :param args: Positional arguments passed to the function.
        :param kwargs: Keyword arguments passed to the function.
            
        :return: A string representing the cache key.
        """

        signature = self._normalize_arguments(func, args, kwargs)
        hashed = self._hash(signature)

        return f"{self.prefix}:{func.__module__}.{func.__qualname__}:{hashed}"
    
    def _normalize_arguments(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Normalize function arguments into a JSON-serializable structure.
        :param func: The target function.
        :param args: Positional arguments.
        :param kwargs: Keyword arguments.
        :return: A JSON-serializable representation of the arguments."""

        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()

        return self._make_json_safe(bound.arguments)
    

    def _make_json_safe(self, obj: Any) -> Any:
        """
        Recursively convert an object into a JSON-serializable structure.
        Handles common FastAPI types like Pydantic models, datetime, UUID, etc.
        :param obj: The object to convert.
        :return: A JSON-serializable representation of the object.
        """

        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        
        if isinstance(obj, UUID):
            return str(obj)
        
        if isinstance(obj, Decimal):
            return str(obj)
        
        if isinstance(obj, Enum):
            return obj.value
        
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        
        try:
            from pydantic import BaseModel
            if isinstance(obj, BaseModel):
                return self._make_json_safe(obj.model_dump())
        except ImportError:
            pass
        
        if hasattr(obj, "__dataclass_fields__"):
            from dataclasses import asdict
            return self._make_json_safe(asdict(obj))
        
        if isinstance(obj, (list, tuple)):
            return [self._make_json_safe(item) for item in obj]
        
        if isinstance(obj, dict):
            return {
                str(key): self._make_json_safe(value)
                for key, value in obj.items()
            }
        
        # Fallback to string representation for unsupported types
        return repr(obj)
    
    def _hash(self, data: dict[str, Any]) -> str:
        """
        Generate a SHA256 hash of the given data.
        :param data: Data to hash
        :return: Hexadecimal hash string
        """
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()