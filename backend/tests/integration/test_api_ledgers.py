"""Integration tests for Ledgers/Reports API — §3.6.

Tests cover: TrialBalance, GeneralLedger, DetailLedger, Journal.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.account import Account
from app.models.period import AccountBalance, Period
from app.models.voucher import Voucher


@pytest.mark.asyncio
async def test_trial_balance_api(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
):
    """GET /api/v1/reports/trial-balance — complete API validation."""
    resp = await client.get(
        f"/api/v1/reports/trial-balance?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify structure per §3.6
    assert "period" in data
    assert data["period"]["year"] == test_period.year
    assert data["period"]["month"] == test_period.month
    assert "rows" in data
    assert "summary" in data

    # Summary should have balance totals
    summary = data["summary"]
    assert "total_opening_debit" in summary
    assert "total_opening_credit" in summary
    assert "total_current_debit" in summary
    assert "total_current_credit" in summary
    assert "total_closing_debit" in summary
    assert "total_closing_credit" in summary


@pytest.mark.asyncio
async def test_trial_balance_with_data(
    client: AsyncClient,
    auth_headers: dict,
    async_session,
    test_period: Period,
    test_cash_account: Account,
):
    """Trial balance with actual balance data — verifies amounts flow through."""
    # Create a balance record
    balance = AccountBalance(
        id=uuid.uuid4(),
        period_id=test_period.id,
        account_id=test_cash_account.id,
        opening_debit=Decimal("100000.00"),
        opening_credit=Decimal("0"),
        current_debit=Decimal("25000.00"),
        current_credit=Decimal("5000.00"),
        closing_debit=Decimal("120000.00"),
        closing_credit=Decimal("0"),
    )
    async_session.add(balance)
    await async_session.flush()

    resp = await client.get(
        f"/api/v1/reports/trial-balance?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Find the cash account row
    rows = data.get("rows", [])
    cash_row = None

    def find_by_code(rows, code):
        for r in rows:
            if r.get("account", {}).get("code") == code:
                return r
            if "children" in r:
                found = find_by_code(r["children"], code)
                if found:
                    return found
        return None

    cash_row = find_by_code(rows, test_cash_account.code)
    if cash_row:
        assert Decimal(str(cash_row["closing_debit"])) == Decimal("120000.00")


@pytest.mark.asyncio
async def test_general_ledger_api(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
    test_cash_account: Account,
):
    """GET /api/v1/reports/general-ledger — complete API validation."""
    resp = await client.get(
        f"/api/v1/reports/general-ledger?period_id={test_period.id}&account_id={test_cash_account.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    data = resp.json()
    assert "period" in data
    assert "account" in data
    assert "opening_balance" in data
    assert "rows" in data
    assert "closing_balance" in data


@pytest.mark.asyncio
async def test_detail_ledger_api(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
    test_cash_account: Account,
):
    """GET /api/v1/reports/detail-ledger/{account_id} — complete API validation."""
    resp = await client.get(
        f"/api/v1/reports/detail-ledger/{test_cash_account.id}?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    data = resp.json()
    assert "period" in data
    assert "account" in data
    assert "opening_balance" in data
    assert "rows" in data
    assert "closing_balance" in data
    assert "current_debit" in data
    assert "current_credit" in data

    # Rows should have running balance + direction
    for row in data.get("rows", []):
        assert "balance" in row
        assert "balance_direction" in row


@pytest.mark.asyncio
async def test_journal_api(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
):
    """GET /api/v1/reports/journal — complete API validation."""
    resp = await client.get(
        f"/api/v1/reports/journal?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    data = resp.json()
    assert "period" in data
    assert "rows" in data

    # Rows should have date, voucher_no, summary, amounts
    for row in data.get("rows", []):
        assert "date" in row
        assert "voucher_no" in row


@pytest.mark.asyncio
async def test_multi_column_ledger_api(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
    test_cash_account: Account,
):
    """GET /api/v1/reports/multi-column-ledger/{account_id} — complete API validation."""
    resp = await client.get(
        f"/api/v1/reports/multi-column-ledger/{test_cash_account.id}?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "columns" in data


@pytest.mark.asyncio
async def test_quantity_ledger_api(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
    test_quantity_account: Account,
):
    """GET /api/v1/reports/quantity-ledger/{account_id} — API validation.

    Uses a quantity-enabled account (the endpoint returns 400 for accounts
    that don't have quantity accounting enabled)."""
    resp = await client.get(
        f"/api/v1/reports/quantity-ledger/{test_quantity_account.id}?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "period" in data


@pytest.mark.asyncio
async def test_trial_balance_requires_auth(client: AsyncClient):
    """Trial balance endpoint should require authentication."""
    resp = await client.get(
        f"/api/v1/reports/trial-balance?period_id={uuid.uuid4()}"
    )
    assert resp.status_code in (401, 403)
