"""Identifier and literal helpers for the production read-only role."""

import pytest

from ensure_readonly import ident, sql_literal


def test_ident_accepts_plain_names():
    assert ident("accounting_ro", "DB_RO_USER") == "accounting_ro"
    assert ident("core_accounting", "DB_NAME") == "core_accounting"


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
