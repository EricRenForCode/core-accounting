"""P9.1 Backend Tests Complete

Integration tests for Auth API — §3.2.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(
    client: AsyncClient,
    test_user,
):
    """POST /api/v1/auth/login — should return tokens for valid credentials."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "testpass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "tokens" in data
    assert "access_token" in data["tokens"]
    assert "refresh_token" in data["tokens"]
    assert "user" in data
    assert data["user"]["username"] == "testuser"


@pytest.mark.asyncio
async def test_login_invalid_password(
    client: AsyncClient,
    test_user,
):
    """POST /api/v1/auth/login — should return 401 for wrong password."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "wrongpassword",
    })
    # 401 is the correct status for failed authentication (bad credentials).
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(
    client: AsyncClient,
    auth_headers: dict,
):
    """GET /api/v1/auth/me — should return current user info."""
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "username" in data
    assert "role" in data
    assert "permissions" in data


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """GET /api/v1/health — should return 200 with status."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_dashboard(
    client: AsyncClient,
    auth_headers: dict,
    test_period,
):
    """GET /api/v1/dashboard/summary — should return dashboard data."""
    resp = await client.get(
        f"/api/v1/dashboard/summary?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "voucher_counts" in data
    assert "trial_balance" in data
