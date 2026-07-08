"""Targeted regression tests for real bugs fixed in v2/v3 (task-breakdown-v3 P3).

Each test pins a specific past failure so it cannot silently return:
- Audit log serialization of Decimal/date/datetime/UUID (was: JSONB insert crash).
- NL-query generated SQL failing at runtime (was: unhandled 500 + poisoned
  connection causing 401s on subsequent requests).
- AI voucher generation with a nonexistent period (was: LLM called first,
  502 instead of 404 — and tokens wasted).
"""
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.ai import nl_query
from app.core.audit import _serialize_instance
from app.core.errors import AIGenerationFailedError
from app.models.voucher import VoucherEntry


# ── Audit serialization (date/Decimal regression) ─────────────


def test_audit_serialize_handles_decimal_date_uuid():
    """_serialize_instance must map Decimal/date/datetime/UUID to JSON-safe values."""
    entry = VoucherEntry(
        id=uuid.uuid4(),
        voucher_id=uuid.uuid4(),
        row_number=1,
        account_id=uuid.uuid4(),
        summary="回归测试",
        debit_amount=Decimal("123.45"),
        credit_amount=Decimal("0"),
    )
    data = _serialize_instance(entry)
    # The serialized dict must be JSON-dumpable as-is (this was the crash).
    json.dumps(data)
    assert data["debit_amount"] == 123.45
    assert isinstance(data["id"], str)


def test_audit_serialize_datetime_before_date():
    """datetime is a date subclass — must serialize with time component intact."""
    from app.models.voucher import Voucher

    now = datetime(2026, 7, 8, 12, 30, 0, tzinfo=timezone.utc)
    assert isinstance(now, date)  # the trap
    voucher = Voucher(
        id=uuid.uuid4(),
        voucher_no="JZ-2026-07-RG1",
        date=date(2026, 7, 8),
        period_id=uuid.uuid4(),
        status="posted",
        creator_id=uuid.uuid4(),
        source="manual",
        posted_at=now,
    )
    data = _serialize_instance(voucher)
    assert data["posted_at"] == "2026-07-08T12:30:00+00:00"
    assert data["date"] == "2026-07-08"


# ── Audit UPDATE captures old_values (§2.12) ──────────────────


@pytest.mark.asyncio
async def test_audit_update_captures_old_values(async_session):
    """UPDATE on a tracked model must record the pre-change values."""
    from sqlalchemy import select

    from app.core.audit import install_audit_listeners
    from app.models.account import Account
    from app.models.audit import AuditLog

    # Listeners normally install during app lifespan, which ASGITransport
    # tests never run — install explicitly (idempotent).
    install_audit_listeners()

    acct = Account(
        id=uuid.uuid4(),
        code="9901",
        name="旧名称",
        level=1,
        type="asset",
        dc_type="D",
        is_enabled=True,
    )
    async_session.add(acct)
    await async_session.commit()

    acct.name = "新名称"
    await async_session.commit()

    result = await async_session.execute(
        select(AuditLog)
        .where(
            AuditLog.resource_type == "accounts",
            AuditLog.action == "UPDATE",
        )
        .order_by(AuditLog.created_at.desc())
    )
    log = result.scalars().first()
    assert log is not None
    assert log.old_values is not None
    assert log.old_values.get("name") == "旧名称"
    assert log.new_values.get("name") == "新名称"


# ── NL query: runtime SQL failure → clean AI error ────────────


@pytest.mark.asyncio
async def test_nl_query_bad_sql_raises_clean_error(async_session, monkeypatch):
    """LLM-generated SQL that fails at runtime must raise AIGenerationFailedError
    (502), not an unhandled OperationalError."""

    async def fake_invoke(prompt: str, max_retries: int = 2) -> str:
        return json.dumps({"sql": "SELECT definitely_not_a_column FROM accounts"})

    monkeypatch.setattr(nl_query, "invoke_structured", fake_invoke)

    with pytest.raises(AIGenerationFailedError):
        await nl_query.execute_nl_query(
            question="回归: 无效列名", conversation_id=None, ai_db=async_session
        )

    # Session must be left usable (was: poisoned transaction → 401 on next call).
    from sqlalchemy import text

    result = await async_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


# ── NL query: conversation memory feeds follow-up prompts ─────


@pytest.mark.asyncio
async def test_nl_query_includes_conversation_history(async_session, monkeypatch):
    """Prior turns must be included in the prompt so 连续追问 has context."""
    captured: dict = {}

    async def fake_invoke(prompt: str, max_retries: int = 2) -> str:
        captured["prompt"] = prompt
        return json.dumps({"sql": "SELECT 1"})

    async def fake_history(conversation_id):
        return [{"question": "本月管理费用多少", "sql": "SELECT 800"}]

    monkeypatch.setattr(nl_query, "invoke_structured", fake_invoke)
    monkeypatch.setattr(nl_query, "_load_conversation", fake_history)

    resp = await nl_query.execute_nl_query(
        question="那库存现金呢",
        conversation_id=uuid.uuid4(),
        ai_db=async_session,
    )
    assert resp.row_count == 1
    # The prompt must carry the prior turn for the LLM to resolve "那…呢"
    assert "本月管理费用多少" in captured["prompt"]
    assert "SELECT 800" in captured["prompt"]


# ── AI explain: non-SELECT rejected (defense in depth) ────────


@pytest.mark.asyncio
async def test_ai_explain_rejects_non_select(client: AsyncClient, auth_headers):
    """/ai/query/explain must gate non-SELECT SQL like /ai/query does."""
    resp = await client.post(
        "/api/v1/ai/query/explain",
        json={"sql": "UPDATE accounts SET name = 'x'"},
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AI_READONLY_VIOLATION"


# ── AI voucher generate: 404 before any LLM call ──────────────


@pytest.mark.asyncio
async def test_ai_generate_404_without_llm_call(
    client: AsyncClient, auth_headers: dict, monkeypatch
):
    """Nonexistent period must 404 BEFORE the LLM is invoked (no tokens spent)."""
    called = False

    async def fail_if_called(prompt: str, max_retries: int = 2) -> str:
        nonlocal called
        called = True
        return "{}"

    from app.ai import voucher_generator

    monkeypatch.setattr(voucher_generator, "invoke_structured", fail_if_called)

    resp = await client.post(
        "/api/v1/ai/voucher/generate",
        json={"description": "测试", "period_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert called is False
