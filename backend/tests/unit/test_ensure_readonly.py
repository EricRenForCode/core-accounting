"""Identifier and literal helpers for the production read-only role."""

import pytest
from unittest.mock import AsyncMock, MagicMock

import ensure_readonly
from ensure_readonly import ident, sql_literal


def test_ident_accepts_plain_names():
    assert ident("accounting_ro", "DB_RO_USER") == '"accounting_ro"'
    assert ident("core_accounting", "DB_NAME") == '"core_accounting"'


def test_ident_preserves_case_and_quotes_reserved_names():
    assert ident("Accounting_RO", "DB_RO_USER") == '"Accounting_RO"'
    assert ident("select", "DB_NAME") == '"select"'


@pytest.mark.parametrize(
    "value",
    ["", "accounting-ro", "public.users", "accounting_ro;drop", "1role", "has space"],
)
def test_ident_rejects_unsafe_names(value: str):
    with pytest.raises(ValueError):
        ident(value, "DB_RO_USER")


def test_sql_literal_escapes_quotes():
    assert sql_literal("abc") == "'abc'"
    assert sql_literal("a'b") == "'a''b'"


def test_sql_literal_rejects_newlines():
    with pytest.raises(ValueError):
        sql_literal("a\nb")


@pytest.mark.asyncio
@pytest.mark.parametrize("existing", [False, True])
async def test_ensure_uses_same_case_for_lookup_and_role_statements(monkeypatch, existing):
    monkeypatch.setenv("DB_RO_USER", "Accounting_RO")
    monkeypatch.setenv("DB_NAME", "Finance_Books")
    monkeypatch.setenv("DB_RO_PASSWORD", "test_only_password_123")
    result = MagicMock()
    result.scalar.return_value = 1 if existing else None
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=result)
    engine = MagicMock()
    engine.begin.return_value.__aenter__ = AsyncMock(return_value=conn)
    engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    engine.dispose = AsyncMock()
    monkeypatch.setattr(ensure_readonly, "create_async_engine", lambda *a, **kw: engine)

    await ensure_readonly.ensure()

    calls = conn.execute.await_args_list
    assert calls[0].args[1] == {"name": "Accounting_RO"}
    statements = [str(call.args[0]) for call in calls[1:]]
    action = "ALTER" if existing else "CREATE"
    assert statements[0].startswith(f'{action} ROLE "Accounting_RO" ')
    assert 'GRANT CONNECT ON DATABASE "Finance_Books" TO "Accounting_RO"' in statements
    assert all(statement.endswith('TO "Accounting_RO"') for statement in statements[1:])
    engine.dispose.assert_awaited_once()
