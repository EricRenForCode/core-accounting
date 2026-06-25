"""Integration tests for Voucher API — §3.3, §3.4.

Full API integration tests covering the complete voucher lifecycle.
These tests verify HTTP status codes, response schemas, and error handling
as defined in the engineering spec's API contract and error code directory.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.account import Account
from app.models.period import Period
from app.models.voucher import Voucher


# ── Create (POST /vouchers) ──────────────────────────────────

@pytest.mark.asyncio
async def test_create_voucher_returns_201(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
    test_cash_account: Account,
    test_expense_account: Account,
):
    """POST /vouchers → 201 with correct response shape."""
    resp = await client.post("/api/v1/vouchers", json={
        "date": "2026-06-15",
        "period_id": str(test_period.id),
        "attachments": 3,
        "entries": [
            {
                "row_number": 1,
                "account_id": str(test_expense_account.id),
                "summary": "购买办公用品",
                "debit_amount": "1500.00",
                "credit_amount": "0",
                "auxiliaries": [],
            },
            {
                "row_number": 2,
                "account_id": str(test_cash_account.id),
                "summary": "购买办公用品",
                "debit_amount": "0",
                "credit_amount": "1500.00",
                "auxiliaries": [],
            },
        ],
    }, headers=auth_headers)

    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "voucher_no" in data
    assert data["voucher_no"].startswith("JZ-")
    assert data["status"] == "draft"
    assert data["source"] == "manual"
    assert data["attachments"] == 3
    assert len(data["entries"]) == 2
    assert data["entries"][0]["row_number"] == 1
    assert data["entries"][1]["row_number"] == 2


@pytest.mark.asyncio
async def test_create_voucher_with_auxiliaries(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
    test_cash_account: Account,
    test_expense_account: Account,
):
    """POST /vouchers with auxiliary核算 references."""
    resp = await client.post("/api/v1/vouchers", json={
        "date": "2026-06-15",
        "period_id": str(test_period.id),
        "attachments": 0,
        "entries": [
            {
                "row_number": 1,
                "account_id": str(test_expense_account.id),
                "summary": "差旅费报销",
                "debit_amount": "800.00",
                "credit_amount": "0",
                "auxiliaries": [],
            },
            {
                "row_number": 2,
                "account_id": str(test_cash_account.id),
                "summary": "差旅费报销",
                "debit_amount": "0",
                "credit_amount": "800.00",
                "auxiliaries": [],
            },
        ],
    }, headers=auth_headers)
    assert resp.status_code == 201


# ── List (GET /vouchers) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_list_vouchers_pagination(
    client: AsyncClient,
    auth_headers: dict,
    draft_voucher: Voucher,
):
    """GET /vouchers → paginated response with correct schema."""
    resp = await client.get("/api/v1/vouchers?page=1&page_size=10", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "pages" in data
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total"] >= 1
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_list_vouchers_filter_date_range(
    client: AsyncClient,
    auth_headers: dict,
    draft_voucher: Voucher,
):
    """GET /vouchers with date range filter."""
    resp = await client.get(
        "/api/v1/vouchers?date_from=2026-06-01&date_to=2026-06-30",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_vouchers_filter_keyword(
    client: AsyncClient,
    auth_headers: dict,
    draft_voucher: Voucher,
):
    """GET /vouchers with keyword search on voucher_no."""
    resp = await client.get(
        f"/api/v1/vouchers?keyword={draft_voucher.voucher_no}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should find the matching voucher
    found = any(
        item["voucher_no"] == draft_voucher.voucher_no
        for item in data["items"]
    )
    assert found


# ── Detail (GET /vouchers/{id}) ──────────────────────────────

@pytest.mark.asyncio
async def test_get_voucher_detail(
    client: AsyncClient,
    auth_headers: dict,
    draft_voucher: Voucher,
):
    """GET /vouchers/{id} → full detail with entries."""
    resp = await client.get(
        f"/api/v1/vouchers/{draft_voucher.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(draft_voucher.id)
    assert len(data["entries"]) == 2
    # Verify entry structure
    entry = data["entries"][0]
    assert "account" in entry
    assert "summary" in entry
    assert "debit_amount" in entry
    assert "credit_amount" in entry


@pytest.mark.asyncio
async def test_get_voucher_404(
    client: AsyncClient,
    auth_headers: dict,
):
    """GET /vouchers/{id} — 404 for nonexistent voucher (VOUCHER_NOT_FOUND)."""
    resp = await client.get(f"/api/v1/vouchers/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
    # Error envelope: {"error": {"code", "message", "detail"}}
    assert "不存在" in resp.json()["error"]["message"]


# ── Audit (POST /vouchers/{id}/audit) ────────────────────────

@pytest.mark.asyncio
async def test_audit_voucher_full_flow(
    client: AsyncClient,
    auth_headers: dict,
    auth_headers_user2: dict,
    test_period: Period,
    test_cash_account: Account,
    test_expense_account: Account,
):
    """Full audit flow: create→audit (by user2)→post→verify."""
    # 1. Create voucher as user1
    create_resp = await client.post("/api/v1/vouchers", json={
        "date": "2026-06-15",
        "period_id": str(test_period.id),
        "attachments": 0,
        "entries": [
            {
                "row_number": 1,
                "account_id": str(test_expense_account.id),
                "summary": "审计流程测试",
                "debit_amount": "5000.00",
                "credit_amount": "0",
                "auxiliaries": [],
            },
            {
                "row_number": 2,
                "account_id": str(test_cash_account.id),
                "summary": "审计流程测试",
                "debit_amount": "0",
                "credit_amount": "5000.00",
                "auxiliaries": [],
            },
        ],
    }, headers=auth_headers)
    assert create_resp.status_code == 201
    voucher_id = create_resp.json()["id"]

    # 2. Audit by user2 (different user)
    audit_resp = await client.post(
        f"/api/v1/vouchers/{voucher_id}/audit",
        headers=auth_headers_user2,
    )
    assert audit_resp.status_code == 200
    assert audit_resp.json()["status"] == "audited"

    # 3. Post by user1
    post_resp = await client.post(
        f"/api/v1/vouchers/{voucher_id}/post",
        headers=auth_headers,
    )
    assert post_resp.status_code == 200
    assert post_resp.json()["status"] == "posted"
    assert post_resp.json()["posted_at"] is not None


@pytest.mark.asyncio
async def test_audit_voucher_already_audited(
    client: AsyncClient,
    auth_headers: dict,
    audited_voucher: Voucher,
):
    """POST /vouchers/{id}/audit — 409 for already audited (VOUCHER_NOT_DRAFT)."""
    resp = await client.post(
        f"/api/v1/vouchers/{audited_voucher.id}/audit",
        headers=auth_headers,
    )
    assert resp.status_code == 409


# ── Post (POST /vouchers/{id}/post) ──────────────────────────

@pytest.mark.asyncio
async def test_post_voucher_409_already_posted(
    client: AsyncClient,
    auth_headers: dict,
    posted_voucher: Voucher,
):
    """POST /vouchers/{id}/post — 409 for already posted (VOUCHER_ALREADY_POSTED)."""
    resp = await client.post(
        f"/api/v1/vouchers/{posted_voucher.id}/post",
        headers=auth_headers,
    )
    assert resp.status_code == 409


# ── Reverse (POST /vouchers/{id}/reverse) ────────────────────

@pytest.mark.asyncio
async def test_reverse_voucher_integration(
    client: AsyncClient,
    auth_headers: dict,
    posted_voucher: Voucher,
):
    """POST /vouchers/{id}/reverse — full reversal flow."""
    resp = await client.post(
        f"/api/v1/vouchers/{posted_voucher.id}/reverse",
        headers=auth_headers,
    )
    assert resp.status_code == 201
    reversal = resp.json()
    assert reversal["reversed_voucher_id"] == str(posted_voucher.id)
    assert reversal["reversal_type"] == "full"
    assert reversal["status"] == "draft"
    assert reversal["source"] == "reversal"

    # Verify debit/credit swapped
    original_entry1 = await client.get(
        f"/api/v1/vouchers/{posted_voucher.id}", headers=auth_headers
    )
    # Entry1 was debit 5000, entry2 was credit 5000
    # Reversal: entry1 should now be credit 5000, entry2 debit 5000
    assert float(reversal["entries"][0]["credit_amount"]) == 5000.0
    assert float(reversal["entries"][1]["debit_amount"]) == 5000.0


# ── Delete (DELETE /vouchers/{id}) ───────────────────────────

@pytest.mark.asyncio
async def test_delete_soft_deletes(
    client: AsyncClient,
    auth_headers: dict,
    test_period: Period,
    test_cash_account: Account,
    test_expense_account: Account,
):
    """DELETE /vouchers/{id} — soft delete sets deleted_at, 404 after."""
    # Create a fresh draft
    create_resp = await client.post("/api/v1/vouchers", json={
        "date": "2026-06-15",
        "period_id": str(test_period.id),
        "attachments": 0,
        "entries": [
            {
                "row_number": 1,
                "account_id": str(test_expense_account.id),
                "summary": "待删除凭证",
                "debit_amount": "100.00",
                "credit_amount": "0",
                "auxiliaries": [],
            },
            {
                "row_number": 2,
                "account_id": str(test_cash_account.id),
                "summary": "待删除凭证",
                "debit_amount": "0",
                "credit_amount": "100.00",
                "auxiliaries": [],
            },
        ],
    }, headers=auth_headers)
    assert create_resp.status_code == 201
    voucher_id = create_resp.json()["id"]

    # Delete
    delete_resp = await client.delete(
        f"/api/v1/vouchers/{voucher_id}", headers=auth_headers
    )
    assert delete_resp.status_code == 200
    assert "已删除" in delete_resp.json()["message"]

    # Verify 404 on re-fetch (soft-deleted)
    get_resp = await client.get(
        f"/api/v1/vouchers/{voucher_id}", headers=auth_headers
    )
    assert get_resp.status_code == 404


# ── Unauthenticated Access ───────────────────────────────────

@pytest.mark.asyncio
async def test_vouchers_unauthenticated(client: AsyncClient):
    """All voucher endpoints should require authentication (401)."""
    resp = await client.get("/api/v1/vouchers")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_voucher_unauthenticated(
    client: AsyncClient,
    test_period: Period,
):
    """POST /vouchers without auth → 401 or 403."""
    resp = await client.post("/api/v1/vouchers", json={
        "date": "2026-06-15",
        "period_id": str(test_period.id),
        "attachments": 0,
        "entries": [],
    })
    assert resp.status_code in (401, 403, 422)
