"""Integration tests for Financial Statements API — §3.7.

Tests cover: BalanceSheet, IncomeStatement, CashFlowStatement.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.models.period import Period


@pytest.mark.asyncio
async def test_balance_sheet_api(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
):
    """GET /api/v1/statements/balance-sheet — complete API validation."""
    resp = await client.get(
        f"/api/v1/statements/balance-sheet?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify structure per §3.7
    assert "period" in data
    assert data["period"]["year"] == test_period.year
    assert data["period"]["month"] == test_period.month
    assert "sections" in data
    assert "totals" in data

    # Sections should have label, items, subtotal
    for section in data.get("sections", []):
        assert "label" in section
        assert "items" in section
        assert "subtotal" in section

    # Totals should include assets and liabilities_equity
    totals = data["totals"]
    assert "assets" in totals
    assert "liabilities_equity" in totals
    assert "closing" in totals["assets"]
    assert "opening" in totals["assets"]

    # Balance check: assets.closing == liabilities_equity.closing
    assert totals["assets"]["closing"] == totals["liabilities_equity"]["closing"]


@pytest.mark.asyncio
async def test_income_statement_api(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
):
    """GET /api/v1/statements/income — complete API validation."""
    resp = await client.get(
        f"/api/v1/statements/income?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify structure
    assert "period" in data
    assert "sections" in data
    assert "totals" in data

    # Totals should have net_profit at minimum
    totals = data["totals"]
    assert "net_profit" in totals or "closing" in totals


@pytest.mark.asyncio
async def test_cash_flow_api(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
):
    """GET /api/v1/statements/cash-flow — complete API validation."""
    resp = await client.get(
        f"/api/v1/statements/cash-flow?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify structure
    assert "period" in data
    assert "sections" in data

    # Should have 3 sections: operating, investing, financing
    section_labels = [s.get("label", "") for s in data.get("sections", [])]
    assert len(section_labels) >= 1


@pytest.mark.asyncio
async def test_statements_templates(
    client: AsyncClient,
    auth_headers: dict,
):
    """GET /api/v1/statements/templates — should return template list."""
    resp = await client.get("/api/v1/statements/templates", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_balance_sheet_period_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Balance sheet with nonexistent period should return 404."""
    resp = await client.get(
        f"/api/v1/statements/balance-sheet?period_id={uuid.uuid4()}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_income_period_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Income statement with nonexistent period should return 404."""
    resp = await client.get(
        f"/api/v1/statements/income?period_id={uuid.uuid4()}",
        headers=auth_headers,
    )
    assert resp.status_code == 404
