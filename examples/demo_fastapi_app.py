import asyncio
import logging
import os
import time
from pathlib import Path
import sys

# Allow running this demo without installing the package:
#   python examples/demo_fastapi_app.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import redis.asyncio as redis
from fastapi import FastAPI

from fastapi_cacheable import CacheConfig, cache_evict, cache_put, cacheable
from fastapi_cacheable.backend.redis import RedisCacheBackend

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="fastapi-cacheable demo")


@app.on_event("startup")
async def _startup() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_password = os.getenv("REDIS_PASSWORD","pass")

    # Prefer REDIS_URL; optionally allow password injection for convenience.
    # Examples:
    #   REDIS_URL=redis://:password@localhost:6379/0
    #   REDIS_URL=redis://localhost:6379/0  REDIS_PASSWORD=password
    redis_client = redis.Redis.from_url(redis_url, password=redis_password)
    CacheConfig.init(RedisCacheBackend(redis_client, key_prefix="demo"))


@app.get("/users/{user_id}")
@cacheable(namespace="users", key="get_user", ttl=30)
async def get_user(user_id: int) -> dict:
    # Simulate slow work
    await asyncio.sleep(2)
    logger.info("Fetching user %s from source", user_id)
    return {"user_id": user_id, "name": f"user-{user_id}", "ts": time.time()}


@app.post("/users/{user_id}/refresh")
@cache_put(namespace="users", key="get_user", ttl=30)
async def refresh_user(user_id: int) -> dict:
    await asyncio.sleep(2)
    logger.info("Refreshing user %s data", user_id)
    return {"user_id": user_id, "name": f"user-{user_id}", "refreshed": True, "ts": time.time()}


@app.delete("/users/{user_id}")
@cache_evict(namespace="users", key="get_user")
async def evict_user(user_id: int) -> dict:
    # This will evict the cache entry for the same namespace+key and args.
    logger.info("Evicting cache for user %s", user_id)
    return {"evicted": True, "user_id": user_id}


@app.delete("/users/cache")
@cache_evict(namespace="users", all_entries=True)
async def evict_all_users() -> dict:
    logger.info("Evicting cache for all users")
    return {"evicted": "all"}


# Run:
#   1) docker compose -f examples/docker-compose.yml up -d
#   2) uvicorn examples.demo_fastapi_app:app --reload


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError as e:
        raise SystemExit(
            "uvicorn is required to run the demo. Install with: pip install uvicorn fastapi"
        ) from e

    uvicorn.run(
        "examples.demo_fastapi_app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
