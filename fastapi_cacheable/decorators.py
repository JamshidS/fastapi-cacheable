from __future__ import annotations

import functools
import hashlib
import inspect
import json
import logging
from typing import Any, Awaitable, Callable, Optional, ParamSpec, TypeVar, cast

from fastapi_cacheable.config import CacheConfig
from fastapi_cacheable.exceptions import CacheNotInitializedError
from fastapi_cacheable.key_builder import DefaultKeyBuilder, KeyBuilder

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

def _ensure_initialized() -> None:
	if not CacheConfig.is_initialized():
		raise CacheNotInitializedError(
			"CacheConfig is not initialized. Call CacheConfig.init(...) at startup."
		)


def _ensure_async(func: Callable[..., Any]) -> None:
	if not inspect.iscoroutinefunction(func):
		raise TypeError(
			f"Cache decorators require an async function; got {func.__qualname__}."
		)


async def _maybe_await_bool(value: bool | Awaitable[bool]) -> bool:
	if inspect.isawaitable(value):
		return cast(bool, await cast(Awaitable[bool], value))
	return cast(bool, value)


async def _call_condition(
	condition: Callable[..., bool] | Callable[..., Awaitable[bool]],
	*args: Any,
	**kwargs: Any,
) -> bool:
	return await _maybe_await_bool(condition(*args, **kwargs))


async def _call_unless(
	unless: Callable[[Any], bool] | Callable[[Any], Awaitable[bool]],
	result: Any,
) -> bool:
	return await _maybe_await_bool(unless(result))


def _filtered_kwargs_for_key(
	func: Callable[..., Any],
	args: tuple[Any, ...],
	kwargs: dict[str, Any],
	excluded_params: set[str],
) -> dict[str, Any]:
	sig = inspect.signature(func)
	bound = sig.bind_partial(*args, **kwargs)
	bound.apply_defaults()

	return {
		name: value
		for name, value in bound.arguments.items()
		if name not in excluded_params
	}


def _build_cache_key(
	*,
	func: Callable[..., Any],
	args: tuple[Any, ...],
	kwargs: dict[str, Any],
	namespace: str,
	key: Optional[str],
	key_builder: Optional[KeyBuilder],
	excluded_params: Optional[set[str]] = None,
) -> str:
	excluded = excluded_params or {"request", "response", "db", "session", "self"}
	filtered_kwargs = _filtered_kwargs_for_key(func, args, kwargs, excluded)

	# Spring-style keys are typically cache-name + key-hash, not function identity.
	# We still reuse DefaultKeyBuilder's json-safe conversion for argument hashing.
	key_id = key or f"{func.__module__}.{func.__qualname__}"

	json_safe = DefaultKeyBuilder(prefix="_unused")._make_json_safe(filtered_kwargs)
	raw = json.dumps(json_safe, sort_keys=True, separators=(",", ":"))
	args_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

	# If a custom builder is supplied, it can override the final key completely.
	if key_builder is not None:
		try:
			custom = key_builder.build(func, (), filtered_kwargs)
			return custom
		except Exception:
			logger.exception("custom key_builder failed; falling back to default")

	return f"{namespace}:{key_id}:{args_hash}"


def cacheable(
	*,
	namespace: str,
	key: Optional[str] = None,
	ttl: int = 3600,
	key_builder: Optional[KeyBuilder] = None,
	condition: Optional[Callable[..., bool] | Callable[..., Awaitable[bool]]] = None,
	unless: Optional[Callable[[Any], bool] | Callable[[Any], Awaitable[bool]]] = None,
	excluded_params: Optional[set[str]] = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
	"""Cache decorator similar to Spring's @Cacheable.

	Reads from cache first; on miss executes the function and stores the result.
	"""

	def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
		_ensure_async(func)

		@functools.wraps(func)
		async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
			_ensure_initialized()

			if condition is not None:
				should_cache = await _call_condition(condition, *args, **kwargs)
				if not should_cache:
					logger.debug(
						"cacheable(%s): condition false; bypass cache for %s",
						namespace,
						func.__qualname__,
					)
					return await func(*args, **kwargs)

			backend = CacheConfig.get_backend()
			cache_key = _build_cache_key(
				func=func,
				args=cast(tuple[Any, ...], args),
				kwargs=cast(dict[str, Any], kwargs),
				namespace=namespace,
				key=key,
				key_builder=key_builder,
				excluded_params=excluded_params,
			)

			try:
				cached = await backend.get(cache_key)
			except Exception:
				logger.exception("cacheable(%s): backend.get failed", namespace)
				cached = None

			if cached is not None:
				return cast(R, cached)

			result = await func(*args, **kwargs)

			if unless is not None:
				skip_store = await _call_unless(unless, result)
				if skip_store:
					return result

			try:
				await backend.set(cache_key, result, ttl=ttl)
			except Exception:
				logger.exception("cacheable(%s): backend.set failed", namespace)

			return result

		return wrapper

	return decorator


def cache_put(
	*,
	namespace: str,
	key: Optional[str] = None,
	ttl: int = 3600,
	key_builder: Optional[KeyBuilder] = None,
	condition: Optional[Callable[..., bool] | Callable[..., Awaitable[bool]]] = None,
	unless: Optional[Callable[[Any], bool] | Callable[[Any], Awaitable[bool]]] = None,
	excluded_params: Optional[set[str]] = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
	"""Cache decorator similar to Spring's @CachePut.

	Always executes the function; then stores the result (unless skipped).
	"""

	def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
		_ensure_async(func)

		@functools.wraps(func)
		async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
			_ensure_initialized()

			result = await func(*args, **kwargs)

			if condition is not None:
				should_cache = await _call_condition(condition, *args, **kwargs)
				if not should_cache:
					return result

			if unless is not None:
				skip_store = await _call_unless(unless, result)
				if skip_store:
					return result

			backend = CacheConfig.get_backend()
			cache_key = _build_cache_key(
				func=func,
				args=cast(tuple[Any, ...], args),
				kwargs=cast(dict[str, Any], kwargs),
				namespace=namespace,
				key=key,
				key_builder=key_builder,
				excluded_params=excluded_params,
			)

			try:
				await backend.set(cache_key, result, ttl=ttl)
			except Exception:
				logger.exception("cache_put(%s): backend.set failed", namespace)

			return result

		return wrapper

	return decorator


def cache_evict(
	*,
	namespace: Optional[str] = None,
	key: Optional[str] = None,
	all_entries: bool = False,
	before_invocation: bool = False,
	key_builder: Optional[KeyBuilder] = None,
	condition: Optional[Callable[..., bool] | Callable[..., Awaitable[bool]]] = None,
	excluded_params: Optional[set[str]] = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
	"""Cache eviction decorator similar to Spring's @CacheEvict."""

	def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
		_ensure_async(func)

		async def _evict(*args: P.args, **kwargs: P.kwargs) -> None:
			backend = CacheConfig.get_backend()

			if all_entries:
				await backend.clear(namespace)
				return

			if namespace is None:
				raise ValueError(
					"cache_evict requires `namespace` when all_entries=False."
				)

			cache_key = _build_cache_key(
				func=func,
				args=cast(tuple[Any, ...], args),
				kwargs=cast(dict[str, Any], kwargs),
				namespace=namespace,
				key=key,
				key_builder=key_builder,
				excluded_params=excluded_params,
			)
			await backend.delete(cache_key)

		@functools.wraps(func)
		async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
			_ensure_initialized()

			if condition is not None:
				should_evict = await _call_condition(condition, *args, **kwargs)
				if not should_evict:
					return await func(*args, **kwargs)

			if before_invocation:
				try:
					await _evict(*args, **kwargs)
				except Exception:
					logger.exception("cache_evict: eviction failed before invocation")

			result = await func(*args, **kwargs)

			if not before_invocation:
				try:
					await _evict(*args, **kwargs)
				except Exception:
					logger.exception("cache_evict: eviction failed after invocation")

			return result

		return wrapper

	return decorator

