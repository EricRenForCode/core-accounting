"""Rate limiting middleware (spec §4 / task-breakdown-v3 P5).

Fixed-window counters per (client IP, category). Categories:
- login: POST /api/v1/auth/login — brute-force protection
- ai:    /api/v1/ai/*            — cost protection
- write: other POST/PUT/PATCH/DELETE — abuse protection

Counters live in Redis when reachable (works across workers); otherwise an
in-process fallback dict is used. Either way a rate-limit failure must never
break a legitimate request — errors degrade to "allow".

``RATE_LIMIT_ENABLED=false`` (env) disables the middleware (test suite).
Limits are configurable via env for ops tuning.
"""
import os
import time
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.errors import make_error_response

WINDOW_SECONDS = 60

# requests per minute per client IP
DEFAULT_LIMITS = {
    "login": int(os.getenv("RATE_LIMIT_LOGIN_PER_MIN", "10")),
    "ai": int(os.getenv("RATE_LIMIT_AI_PER_MIN", "30")),
    "write": int(os.getenv("RATE_LIMIT_WRITE_PER_MIN", "240")),
}

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# In-process fallback: {key: (window_start_epoch, count)}
_local_counters: dict[str, tuple[int, int]] = {}


def _enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() != "false"


def _categorize(request: Request) -> Optional[str]:
    """Map a request to a rate-limit category, or None if unlimited."""
    path = request.url.path
    if path == "/api/v1/auth/login" and request.method == "POST":
        return "login"
    if path.startswith("/api/v1/ai/"):
        return "ai"
    if request.method in _WRITE_METHODS and path.startswith("/api/v1/"):
        return "write"
    return None


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_local(key: str, limit: int) -> bool:
    """Fixed-window counter in process memory. Returns True if allowed."""
    now = int(time.time())
    window = now - (now % WINDOW_SECONDS)
    start, count = _local_counters.get(key, (window, 0))
    if start != window:
        start, count = window, 0
    count += 1
    _local_counters[key] = (start, count)
    # Opportunistic cleanup so the dict doesn't grow unbounded.
    if len(_local_counters) > 10_000:
        _local_counters.clear()
    return count <= limit


async def _check_redis(key: str, limit: int) -> Optional[bool]:
    """Fixed-window counter in Redis. Returns None if Redis unavailable."""
    try:
        from app.core.cache import get_redis

        r = get_redis()
        now = int(time.time())
        window = now - (now % WINDOW_SECONDS)
        redis_key = f"ratelimit:{key}:{window}"
        count = await r.incr(redis_key)
        if count == 1:
            await r.expire(redis_key, WINDOW_SECONDS * 2)
        return int(count) <= limit
    except Exception:  # noqa: BLE001 — degrade to local counter
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """429 on excessive login / AI / write requests per client IP."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        if not _enabled():
            return await call_next(request)

        category = _categorize(request)
        if category is None:
            return await call_next(request)

        limit = DEFAULT_LIMITS[category]
        key = f"{category}:{_client_ip(request)}"

        allowed = await _check_redis(key, limit)
        if allowed is None:
            allowed = _check_local(key, limit)

        if not allowed:
            return make_error_response(
                429,
                "RATE_LIMITED",
                "请求过于频繁，请稍后再试",
                {"category": category, "limit_per_minute": limit},
            )
        return await call_next(request)
