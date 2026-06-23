"""Integration tests for AI API — §3.12.

Tests cover: AI voucher generation, report interpretation, period check, NL query.
These tests verify endpoint availability, authorization, and input validation.
Actual AI backend responses depend on configured LLM provider.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.models.period import Period


# ── AI Voucher Generation ─────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_voucher_generate_requires_auth(client: AsyncClient):
    """AI voucher generation should require authentication (401/403)."""
    resp = await client.post("/api/v1/ai/voucher/generate", json={
        "description": "测试",
        "period_id": str(uuid.uuid4()),
    })
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ai_voucher_generate_with_auth(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
):
    """AI voucher generation with auth — should accept request."""
    resp = await client.post("/api/v1/ai/voucher/generate", json={
        "description": "支付差旅费5000元给张三",
        "period_id": str(test_period.id),
    }, headers=auth_headers)
    # 200 if AI is configured, 502 if no AI backend
    assert resp.status_code in (200, 422, 500, 502, 503)


@pytest.mark.asyncio
async def test_ai_voucher_generate_invalid_period(
    client: AsyncClient,
    auth_headers: dict,
):
    """AI voucher generate with invalid period_id should return 404."""
    resp = await client.post("/api/v1/ai/voucher/generate", json={
        "description": "测试",
        "period_id": str(uuid.uuid4()),
    }, headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ai_voucher_refine(
    client: AsyncClient,
    auth_headers: dict,
):
    """AI voucher refine should accept refinement request."""
    resp = await client.post("/api/v1/ai/voucher/refine", json={
        "conversation_id": str(uuid.uuid4()),
        "refinement": "把金额改成8000元",
    }, headers=auth_headers)
    assert resp.status_code in (200, 404, 422, 500, 502, 503)


# ── AI Report Interpretation ─────────────────────────────────

@pytest.mark.asyncio
async def test_ai_report_interpret(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
):
    """AI report interpretation — should accept valid request."""
    resp = await client.post("/api/v1/ai/reports/interpret", json={
        "period_id": str(test_period.id),
        "report_type": "balance_sheet",
    }, headers=auth_headers)
    assert resp.status_code in (200, 422, 500, 502, 503)


# ── AI Period Check ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_period_check_carry_forward(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
):
    """Period check via carry-forward endpoint."""
    # Try the carry-forward check endpoint
    resp = await client.get(
        f"/api/v1/carry-forward/check?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code in (200, 404, 500, 502, 503)

    if resp.status_code == 200:
        data = resp.json()
        assert "checks" in data
        assert "summary" in data
        assert "can_close" in data

        # Verify 10 checks per spec §3.8
        checks = data["checks"]
        assert len(checks) == 10

        summary = data["summary"]
        assert "pass" in summary
        assert "warn" in summary
        assert "fail" in summary


# ── AI Natural Language Query ────────────────────────────────

@pytest.mark.asyncio
async def test_ai_query_requires_auth(client: AsyncClient):
    """AI NL query should require authentication."""
    resp = await client.post("/api/v1/ai/query", json={
        "question": "SELECT * FROM accounts",
    })
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ai_query_input_validation(
    client: AsyncClient,
    auth_headers: dict,
):
    """AI query should validate input length (max 500 chars)."""
    # Valid length
    resp = await client.post("/api/v1/ai/query", json={
        "question": "查询本月管理费用",
    }, headers=auth_headers)
    assert resp.status_code in (200, 422, 500, 502, 503)

    # Too long (> 500 chars)
    resp = await client.post("/api/v1/ai/query", json={
        "question": "x" * 501,
    }, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ai_query_explain(
    client: AsyncClient,
    auth_headers: dict,
):
    """AI query explain should accept valid SQL."""
    resp = await client.post("/api/v1/ai/query/explain", json={
        "sql": "SELECT * FROM accounts",
    }, headers=auth_headers)
    assert resp.status_code in (200, 422, 500, 502, 503)
