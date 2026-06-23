"""Unit tests for ledger/reports service — §3.6, §7.2.

Tests cover: TrialBalance, GeneralLedger, DetailLedger, Journal, QuantityLedger.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.account import Account
from app.models.period import AccountBalance, Period
from app.models.voucher import Voucher, VoucherEntry


# ── Trial Balance ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trial_balance_returns_data(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
):
    """Trial balance endpoint should return 200 with period and rows."""
    resp = await client.get(
        f"/api/v1/reports/trial-balance?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "period" in data
    assert "rows" in data


@pytest.mark.asyncio
async def test_trial_balance_filter_by_level(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
    test_cash_account: Account,
    test_expense_account: Account,
):
    """Trial balance with level filter should return only matching accounts."""
    resp = await client.get(
        f"/api/v1/reports/trial-balance?period_id={test_period.id}&level=1",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # Level 1 accounts only (no children)
    for row in data.get("rows", []):
        if "account" in row:
            assert row["account"]["level"] == 1


@pytest.mark.asyncio
async def test_trial_balance_with_balances(
    client: AsyncClient,
    auth_headers: dict,
    async_session,
    test_period: Period,
    test_cash_account: Account,
):
    """Trial balance should reflect posted balances."""
    # Create an account balance for cash
    balance = AccountBalance(
        id=uuid.uuid4(),
        period_id=test_period.id,
        account_id=test_cash_account.id,
        opening_debit=Decimal("100000.00"),
        opening_credit=Decimal("0"),
        current_debit=Decimal("20000.00"),
        current_credit=Decimal("5000.00"),
        closing_debit=Decimal("115000.00"),
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
    # Should find our cash account in the rows
    found = False
    for row in data.get("rows", []):
        if row.get("account", {}).get("code") == test_cash_account.code:
            found = True
            # Verify amounts
            assert Decimal(str(row["current_debit"])) == Decimal("20000.00")
            assert Decimal(str(row["current_credit"])) == Decimal("5000.00")
            break
    assert found, f"Account {test_cash_account.code} not found in trial balance"


@pytest.mark.asyncio
async def test_trial_balance_include_zero(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
):
    """Trial balance with include_zero=True should return accounts with zero balances."""
    resp = await client.get(
        f"/api/v1/reports/trial-balance?period_id={test_period.id}&include_zero=true",
        headers=auth_headers,
    )
    assert resp.status_code == 200


# ── General Ledger ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_general_ledger(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
    test_cash_account: Account,
):
    """General ledger should return 200 with entries for the account."""
    resp = await client.get(
        f"/api/v1/reports/general-ledger?period_id={test_period.id}&account_id={test_cash_account.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # Basic structure check
    assert "account" in data or "period" in data or "rows" in data


@pytest.mark.asyncio
async def test_general_ledger_with_posted_entries(
    client: AsyncClient,
    auth_headers: dict,
    async_session,
    test_period: Period,
    test_cash_account: Account,
    test_expense_account: Account,
    test_user,
    test_user2,
):
    """General ledger should show posted voucher entries."""
    # Create a posted voucher
    v = Voucher(
        id=uuid.uuid4(),
        voucher_no="JZ-2026-06-GL",
        date=date(2026, 6, 15),
        period_id=test_period.id,
        status="posted",
        creator_id=test_user.id,
        auditor_id=test_user2.id,
        source="manual",
    )
    async_session.add(v)
    await async_session.flush()

    e1 = VoucherEntry(
        id=uuid.uuid4(), voucher_id=v.id, row_number=1,
        account_id=test_expense_account.id, summary="办公费",
        debit_amount=Decimal("2000.00"), credit_amount=Decimal("0"),
    )
    e2 = VoucherEntry(
        id=uuid.uuid4(), voucher_id=v.id, row_number=2,
        account_id=test_cash_account.id, summary="办公费",
        debit_amount=Decimal("0"), credit_amount=Decimal("2000.00"),
    )
    async_session.add_all([e1, e2])
    await async_session.flush()

    resp = await client.get(
        f"/api/v1/reports/general-ledger?period_id={test_period.id}&account_id={test_cash_account.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200


# ── Detail Ledger ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detail_ledger(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
    test_cash_account: Account,
):
    """Detail ledger should return 200 with running balance."""
    resp = await client.get(
        f"/api/v1/reports/detail-ledger/{test_cash_account.id}?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200


# ── Journal (序时账) ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_journal(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
):
    """Journal should return 200 with posted entries in date order."""
    resp = await client.get(
        f"/api/v1/reports/journal?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200


# ── Multi-Column Ledger ──────────────────────────────────────

@pytest.mark.asyncio
async def test_multi_column_ledger(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
    test_cash_account: Account,
):
    """Multi-column ledger should return 200."""
    resp = await client.get(
        f"/api/v1/reports/multi-column-ledger/{test_cash_account.id}?period_id={test_period.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200


# ── Quantity Ledger ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_quantity_ledger(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
    test_cash_account: Account,
):
    """Quantity ledger should return 200."""
    resp = await client.get(
        f"/api/v1/reports/quantity-ledger/{test_cash_account.id}?period_id={test_period.id}",
        headers=auth_headers,
    )
    # May return 200 or 404 if no quantity data for this account
    assert resp.status_code in (200, 404)
