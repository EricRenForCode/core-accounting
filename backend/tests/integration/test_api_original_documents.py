"""Integration tests for /api/v1/original-documents (原始凭证/票据附件)."""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.original_document import OriginalDocument
from app.models.voucher import Voucher

from tests.conftest import _create_test_user

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    """Isolate file storage per test (routes read Settings lazily)."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    return tmp_path / "uploads"


async def _upload(
    client: AsyncClient,
    headers: dict,
    file_name: str = "travel_差旅报销_2026-06-15_500.00.pdf",
    document_type: str = "other",
) -> dict:
    resp = await client.post(
        "/api/v1/original-documents/upload",
        headers=headers,
        files={"file": (file_name, b"%PDF-1.4 fake pdf content", "application/pdf")},
        data={"document_type": document_type},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Upload ────────────────────────────────────────────────────

async def test_upload_creates_record(client, auth_headers, upload_dir):
    doc = await _upload(client, auth_headers)
    assert doc["status"] == "uploaded"
    assert doc["file_name"].endswith(".pdf")
    assert doc["file_size"] > 0
    assert doc["voucher_id"] is None
    # File stored under server-generated name, not the client name
    stored = list((upload_dir / "original_documents").iterdir())
    assert len(stored) == 1
    assert "travel" not in stored[0].name


async def test_upload_rejects_bad_extension(client, auth_headers):
    resp = await client.post(
        "/api/v1/original-documents/upload",
        headers=auth_headers,
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert resp.status_code == 400


async def test_upload_sanitizes_path_traversal(client, auth_headers):
    doc = await _upload(client, auth_headers, file_name="../../etc/passwd.pdf")
    assert "/" not in doc["file_name"]
    assert ".." not in doc["file_name"]


async def test_upload_requires_permission(client, async_session: AsyncSession):
    user = await _create_test_user(async_session, username="readonly1")
    token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        role="finance_staff",
        permissions=["report:read"],
    )
    resp = await client.post(
        "/api/v1/original-documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("a.pdf", b"x", "application/pdf")},
    )
    assert resp.status_code == 403


# ── List / Detail / File ──────────────────────────────────────

async def test_list_and_filters(client, auth_headers):
    await _upload(client, auth_headers, file_name="rent_房租_3000.pdf")
    await _upload(client, auth_headers, file_name="bank_回单.png")

    resp = await client.get("/api/v1/original-documents", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2

    resp = await client.get(
        "/api/v1/original-documents",
        headers=auth_headers,
        params={"keyword": "房租"},
    )
    assert resp.json()["total"] == 1

    resp = await client.get(
        "/api/v1/original-documents",
        headers=auth_headers,
        params={"status": "uploaded"},
    )
    assert resp.json()["total"] == 2


async def test_list_allows_report_reader(client, async_session: AsyncSession):
    """report:read alone (no voucher:create) can view the台账."""
    user = await _create_test_user(async_session, username="readonly2")
    token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        role="finance_staff",
        permissions=["report:read"],
    )
    resp = await client.get(
        "/api/v1/original-documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


async def test_get_detail_and_file(client, auth_headers):
    doc = await _upload(client, auth_headers)
    resp = await client.get(
        f"/api/v1/original-documents/{doc['id']}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == doc["id"]

    resp = await client.get(
        f"/api/v1/original-documents/{doc['id']}/file", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


async def test_get_missing_returns_404(client, auth_headers):
    resp = await client.get(
        f"/api/v1/original-documents/{uuid.uuid4()}", headers=auth_headers
    )
    assert resp.status_code == 404


# ── Recognition ───────────────────────────────────────────────

async def test_recognize_travel_document(client, auth_headers):
    doc = await _upload(client, auth_headers)
    resp = await client.post(
        f"/api/v1/original-documents/{doc['id']}/recognize", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("recognized", "needs_review")
    assert body["document_type"] == "reimbursement"
    assert Decimal(body["amount"]) == Decimal("500.00")
    assert body["issue_date"] == "2026-06-15"
    entries = body["recognized_fields"]["suggested_entries"]
    assert len(entries) == 2
    assert entries[0]["account_code"] == "6602"
    assert entries[1]["account_code"] == "1001"


async def test_recognize_unknown_needs_review(client, auth_headers):
    doc = await _upload(client, auth_headers, file_name="scan001.png")
    resp = await client.post(
        f"/api/v1/original-documents/{doc['id']}/recognize", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "needs_review"
    assert body["recognized_fields"]["warnings"]


# ── 人工校对 ───────────────────────────────────────────────────

async def test_update_fields(client, auth_headers):
    doc = await _upload(client, auth_headers)
    resp = await client.put(
        f"/api/v1/original-documents/{doc['id']}",
        headers=auth_headers,
        json={
            "counterparty_name": "携程商旅",
            "invoice_no": "INV-2026-001",
            "total_amount": "520.00",
            "document_type": "invoice",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["counterparty_name"] == "携程商旅"
    assert body["invoice_no"] == "INV-2026-001"
    assert body["document_type"] == "invoice"
    assert body["status"] == "needs_review"  # uploaded → needs_review after edit


async def test_update_rejects_bad_document_type(client, auth_headers):
    doc = await _upload(client, auth_headers)
    resp = await client.put(
        f"/api/v1/original-documents/{doc['id']}",
        headers=auth_headers,
        json={"document_type": "nonsense"},
    )
    assert resp.status_code == 400


# ── Voucher draft generation ─────────────────────────────────

async def test_create_voucher_draft(
    client, auth_headers, test_period, test_accounts, async_session: AsyncSession
):
    doc = await _upload(client, auth_headers)
    await client.post(
        f"/api/v1/original-documents/{doc['id']}/recognize", headers=auth_headers
    )

    resp = await client.post(
        f"/api/v1/original-documents/{doc['id']}/create-voucher-draft",
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["voucher_no"]

    # Voucher is a DRAFT sourced from the document, balanced 500/500
    result = await async_session.execute(
        select(Voucher).where(Voucher.id == uuid.UUID(body["voucher_id"]))
    )
    voucher = result.scalar_one()
    assert voucher.status == "draft"
    assert voucher.source == "document"

    # Document now linked + status voucher_created
    detail = await client.get(
        f"/api/v1/original-documents/{doc['id']}", headers=auth_headers
    )
    assert detail.json()["status"] == "voucher_created"
    assert detail.json()["voucher_id"] == body["voucher_id"]
    assert detail.json()["voucher_no"] == body["voucher_no"]


async def test_create_voucher_draft_requires_entries(client, auth_headers, test_period):
    doc = await _upload(client, auth_headers, file_name="contract_合同.pdf")
    await client.post(
        f"/api/v1/original-documents/{doc['id']}/recognize", headers=auth_headers
    )
    resp = await client.post(
        f"/api/v1/original-documents/{doc['id']}/create-voucher-draft",
        headers=auth_headers,
    )
    assert resp.status_code == 409


async def test_create_voucher_draft_twice_conflicts(
    client, auth_headers, test_period, test_accounts
):
    doc = await _upload(client, auth_headers)
    await client.post(
        f"/api/v1/original-documents/{doc['id']}/recognize", headers=auth_headers
    )
    first = await client.post(
        f"/api/v1/original-documents/{doc['id']}/create-voucher-draft",
        headers=auth_headers,
    )
    assert first.status_code == 201
    second = await client.post(
        f"/api/v1/original-documents/{doc['id']}/create-voucher-draft",
        headers=auth_headers,
    )
    assert second.status_code == 409


# ── Link existing voucher ─────────────────────────────────────

async def test_link_existing_voucher(client, auth_headers, draft_voucher):
    doc = await _upload(client, auth_headers)
    resp = await client.post(
        f"/api/v1/original-documents/{doc['id']}/link-voucher",
        headers=auth_headers,
        json={"voucher_id": str(draft_voucher.id)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["voucher_id"] == str(draft_voucher.id)
    assert body["status"] == "voucher_created"

    # Reverse lookup via voucher_id filter (used by VoucherDetail page)
    listed = await client.get(
        "/api/v1/original-documents",
        headers=auth_headers,
        params={"voucher_id": str(draft_voucher.id)},
    )
    assert listed.json()["total"] == 1


async def test_link_missing_voucher_404(client, auth_headers):
    doc = await _upload(client, auth_headers)
    resp = await client.post(
        f"/api/v1/original-documents/{doc['id']}/link-voucher",
        headers=auth_headers,
        json={"voucher_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


# ── Delete ────────────────────────────────────────────────────

async def test_delete_unlinked_document(
    client, auth_headers, upload_dir, async_session: AsyncSession
):
    doc = await _upload(client, auth_headers)
    resp = await client.delete(
        f"/api/v1/original-documents/{doc['id']}", headers=auth_headers
    )
    assert resp.status_code == 200

    result = await async_session.execute(
        select(OriginalDocument).where(OriginalDocument.id == uuid.UUID(doc["id"]))
    )
    assert result.scalar_one_or_none() is None
    assert list((upload_dir / "original_documents").iterdir()) == []


async def test_delete_linked_document_conflicts(client, auth_headers, draft_voucher):
    doc = await _upload(client, auth_headers)
    await client.post(
        f"/api/v1/original-documents/{doc['id']}/link-voucher",
        headers=auth_headers,
        json={"voucher_id": str(draft_voucher.id)},
    )
    resp = await client.delete(
        f"/api/v1/original-documents/{doc['id']}", headers=auth_headers
    )
    assert resp.status_code == 409
