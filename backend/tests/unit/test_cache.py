"""Unit tests for the Redis cache layer (P4) — graceful degradation focus."""
import pytest

from app.core import cache as cache_mod


@pytest.mark.asyncio
async def test_cache_disabled_via_env(monkeypatch):
    """CACHE_ENABLED=false must make all helpers no-ops (test-suite mode)."""
    monkeypatch.setenv("CACHE_ENABLED", "false")
    assert await cache_mod.cache_get_json("k") is None
    # set/delete must not raise even with no Redis reachable
    await cache_mod.cache_set_json("k", {"a": 1}, 60)
    await cache_mod.cache_delete_pattern("k*")


@pytest.mark.asyncio
async def test_cache_degrades_to_miss_when_redis_down(monkeypatch):
    """With cache enabled but Redis unreachable, helpers must swallow errors."""
    monkeypatch.setenv("CACHE_ENABLED", "true")
    # Point the client at a port nothing listens on; force re-creation.
    monkeypatch.setattr(cache_mod.settings, "REDIS_URL", "redis://127.0.0.1:1/0")
    monkeypatch.setattr(cache_mod, "_client", None)

    assert await cache_mod.cache_get_json("k") is None
    await cache_mod.cache_set_json("k", {"a": 1}, 60)  # must not raise
    await cache_mod.cache_delete_pattern("k*")  # must not raise

    # Reset the module-level client so later tests don't reuse the bad URL.
    monkeypatch.setattr(cache_mod, "_client", None)


@pytest.mark.asyncio
async def test_cache_roundtrip_with_fake_redis(monkeypatch):
    """cache_set_json / cache_get_json round-trip via an in-memory fake."""

    class FakeRedis:
        def __init__(self):
            self.store: dict[str, str] = {}

        async def get(self, key):
            return self.store.get(key)

        async def setex(self, key, ttl, value):
            assert ttl > 0
            self.store[key] = value

        async def delete(self, *keys):
            for k in keys:
                self.store.pop(k, None)

        def scan_iter(self, match=None, count=100):
            import fnmatch

            keys = [k for k in self.store if fnmatch.fnmatch(k, match or "*")]

            async def gen():
                for k in keys:
                    yield k

            return gen()

    fake = FakeRedis()
    monkeypatch.setenv("CACHE_ENABLED", "true")
    monkeypatch.setattr(cache_mod, "get_redis", lambda: fake)

    await cache_mod.cache_set_json("trial-balance:p1:all:False", {"rows": [1]}, 60)
    assert await cache_mod.cache_get_json("trial-balance:p1:all:False") == {
        "rows": [1]
    }

    await cache_mod.cache_delete_pattern("trial-balance:p1*")
    assert await cache_mod.cache_get_json("trial-balance:p1:all:False") is None
