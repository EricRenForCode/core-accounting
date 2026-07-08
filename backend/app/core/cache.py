"""Redis cache helpers with graceful degradation (task-breakdown-v3 P4).

Design rules:
- Cache failures must NEVER break a request: every helper swallows Redis
  errors and behaves as a cache miss / no-op.
- Values are stored as JSON strings; callers pass/receive JSON-safe dicts
  (use pydantic ``model_dump(mode="json")``).
- ``CACHE_ENABLED=false`` (env) turns the whole layer into a no-op — used
  by the test suite so runs never cross-contaminate through a live Redis.
"""
import json
import logging
import os
from typing import Any, Optional

import redis.asyncio as aioredis

from app.config import Settings

logger = logging.getLogger(__name__)

settings = Settings()

# Cache TTLs (seconds)
ACCOUNT_TREE_TTL = 300  # §P4: account tree, 5 min stale allowed
TRIAL_BALANCE_TTL = 600  # invalidated on posting anyway; TTL is a backstop

_client: Optional[aioredis.Redis] = None


def _enabled() -> bool:
    return os.getenv("CACHE_ENABLED", "true").strip().lower() != "false"


def get_redis() -> aioredis.Redis:
    """Lazily create the shared Redis client (short timeouts, no retries)."""
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )
    return _client


async def cache_get_json(key: str) -> Optional[Any]:
    """Return the cached JSON value for ``key``, or None on miss/error."""
    if not _enabled():
        return None
    try:
        raw = await get_redis().get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as e:  # noqa: BLE001 — cache must never break a request
        logger.debug("cache_get_json(%s) degraded to miss: %s", key, e)
        return None


async def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    """Store a JSON-safe value under ``key`` with a TTL. Errors are ignored."""
    if not _enabled():
        return
    try:
        await get_redis().setex(key, ttl_seconds, json.dumps(value))
    except Exception as e:  # noqa: BLE001
        logger.debug("cache_set_json(%s) skipped: %s", key, e)


async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching ``pattern`` (e.g. 'trial-balance:{id}*')."""
    if not _enabled():
        return
    try:
        r = get_redis()
        keys = [k async for k in r.scan_iter(match=pattern, count=100)]
        if keys:
            await r.delete(*keys)
    except Exception as e:  # noqa: BLE001
        logger.debug("cache_delete_pattern(%s) skipped: %s", pattern, e)
