# fastapi-cacheable
Spring-style declarative caching for async Python (FastAPI-friendly)

This library provides async decorators inspired by Spring Boot:
- `@cacheable`: read-through cache (hit returns cached value, miss computes + stores)
- `@cache_put`: always compute, then store
- `@cache_evict`: evict one key or a whole namespace

It ships with a Redis backend using `redis.asyncio`.

## Install

From source (recommended while developing):

	pip install -e .

Optional dependencies:

	pip install -e ".[msgpack,pydantic]"

## Quickstart (FastAPI + Redis)

1) Initialize the cache once at startup:

	import redis.asyncio as redis

	from fastapi_cacheable import CacheConfig
	from fastapi_cacheable.backend.redis import RedisCacheBackend

	redis_client = redis.Redis.from_url("redis://localhost:6379/0")
	CacheConfig.init(
		RedisCacheBackend(redis_client, key_prefix="myapp"),
	)

2) Decorate async functions/routes:

	from fastapi import FastAPI
	from fastapi_cacheable import cacheable, cache_evict, cache_put

	app = FastAPI()


	@app.get("/users/{user_id}")
	@cacheable(namespace="users", key="get_user", ttl=60)
	async def get_user(user_id: int) -> dict:
		# pretend this is slow
		return {"user_id": user_id, "name": f"user-{user_id}"}


	@app.post("/users/{user_id}/refresh")
	@cache_put(namespace="users", key="get_user", ttl=60)
	async def refresh_user(user_id: int) -> dict:
		# recompute and overwrite cached entry
		return {"user_id": user_id, "name": f"user-{user_id}", "refreshed": True}


	@app.delete("/users/cache")
	@cache_evict(namespace="users", all_entries=True)
	async def clear_user_cache() -> dict:
		return {"ok": True}

## How keys work

Cache keys are generated as:

	{namespace}:{key}:{args_hash}

Where:
- `namespace` is the cache region (similar to Spring's cache name)
- `key` is a stable string you choose (recommended). If omitted, a default based on the function name is used.
- `args_hash` is a SHA-256 hash of the function arguments (after excluding common dependency params).

The explicit `key` parameter lets `@cache_evict` evict entries created by a different function, as long as you use the same `namespace` + `key`.

### Excluding dependency parameters

By default, these parameters are excluded from the key:

	{"request", "response", "db", "session", "self"}

You can override with `excluded_params={...}`.

## Conditions (Spring-like)

Decorators support `condition` and `unless`.

	from fastapi_cacheable import cacheable


	@cacheable(
		namespace="users",
		key="get_user",
		ttl=60,
		condition=lambda user_id: user_id > 0,
		unless=lambda result: result is None,
	)
	async def get_user(user_id: int):
		...

Both `condition` and `unless` can be sync or async callables.

## Backends

Backends implement `BaseCacheBackend` in [fastapi_cacheable/backend/base.py](fastapi_cacheable/backend/base.py).

Redis backend: [fastapi_cacheable/backend/redis.py](fastapi_cacheable/backend/redis.py)

Notes:
- `RedisCacheBackend.clear(namespace=...)` uses Redis `KEYS` for explicit eviction.
- Values are serialized via [fastapi_cacheable/serializer.py](fastapi_cacheable/serializer.py) (JSON by default).

## Demo

See [examples/demo_fastapi_app.py](examples/demo_fastapi_app.py) and [examples/docker-compose.yml](examples/docker-compose.yml).
