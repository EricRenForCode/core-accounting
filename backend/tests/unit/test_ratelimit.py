"""Rate limiting middleware tests (P5)."""
import pytest
from httpx import AsyncClient

from app.core import ratelimit as rl


def test_categorize_login_ai_write_read():
    """Requests map to the right rate-limit category."""

    class FakeURL:
        def __init__(self, path):
            self.path = path

    class FakeRequest:
        def __init__(self, method, path):
            self.method = method
            self.url = FakeURL(path)

    assert rl._categorize(FakeRequest("POST", "/api/v1/auth/login")) == "login"
    assert rl._categorize(FakeRequest("POST", "/api/v1/ai/query")) == "ai"
    assert rl._categorize(FakeRequest("GET", "/api/v1/ai/something")) == "ai"
    assert rl._categorize(FakeRequest("POST", "/api/v1/vouchers")) == "write"
    assert rl._categorize(FakeRequest("DELETE", "/api/v1/accounts/x")) == "write"
    assert rl._categorize(FakeRequest("GET", "/api/v1/accounts")) is None
    assert rl._categorize(FakeRequest("GET", "/api/v1/reports/trial-balance")) is None


def test_local_counter_blocks_over_limit(monkeypatch):
    """The in-process fallback counter enforces the fixed-window limit."""
    monkeypatch.setattr(rl, "_local_counters", {})
    key = "login:1.2.3.4"
    allowed = [rl._check_local(key, 3) for _ in range(5)]
    assert allowed == [True, True, True, False, False]


@pytest.mark.asyncio
async def test_login_rate_limited_end_to_end(client: AsyncClient, monkeypatch):
    """Hammering /auth/login gets a 429 once over the per-minute limit."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setitem(rl.DEFAULT_LIMITS, "login", 3)
    # Force the in-process counter (no Redis dependency in tests).
    async def no_redis(key, limit):
        return None

    monkeypatch.setattr(rl, "_check_redis", no_redis)
    monkeypatch.setattr(rl, "_local_counters", {})

    statuses = []
    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "wrongpass"},
        )
        statuses.append(resp.status_code)

    # First 3 attempts hit auth (401); the rest are rate limited.
    assert statuses[:3] == [401, 401, 401]
    assert statuses[3:] == [429, 429]
    # 429 body uses the standard error envelope
    assert resp.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_reads_never_rate_limited(client: AsyncClient, auth_headers, monkeypatch):
    """GET endpoints are not throttled even with tiny limits."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setitem(rl.DEFAULT_LIMITS, "write", 1)
    monkeypatch.setattr(rl, "_local_counters", {})

    for _ in range(4):
        resp = await client.get("/api/v1/accounts", headers=auth_headers)
        assert resp.status_code == 200
