"""AI Natural Language → SQL Query with security measures (§4, §3.12)."""

import json
import time
import uuid as _uuid

import sqlparse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_client import invoke_structured
from app.core.errors import (
    AIGenerationFailedError,
    AIInvalidResponseError,
    ReadOnlyViolationError,
)
from app.schemas.period import AIQueryResponse


def validate_readonly_sql(sql: str) -> str:
    """Validate that SQL contains only SELECT statements and enforce LIMIT.

    Args:
        sql: Raw SQL string from LLM.

    Returns:
        Validated SQL string (with LIMIT appended if missing).

    Raises:
        ReadOnlyViolationError: If any non-SELECT statement is detected.
    """
    parsed = sqlparse.parse(sql)

    for stmt in parsed:
        if stmt.get_type() != "SELECT":
            raise ReadOnlyViolationError(stmt.get_type())

    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(";").rstrip() + " LIMIT 1000"

    return sql


def extract_sql_from_llm_response(raw_response: str) -> str:
    """Extract SQL from DeepSeek JSON mode response or legacy bare SQL."""
    sql = raw_response.strip()
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[1] if "\n" in sql else sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]
        sql = sql.strip()

    try:
        parsed = json.loads(sql)
        if isinstance(parsed, dict):
            sql = str(parsed.get("sql") or parsed.get("query") or "")
    except json.JSONDecodeError:
        pass

    sql = sql.strip()
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[1] if "\n" in sql else sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]
        sql = sql.strip()

    if not sql:
        raise AIInvalidResponseError("missing sql field")
    return sql


def get_db_schema_summary() -> str:
    """Build a concise schema summary for the LLM prompt."""
    return """
Tables (PostgreSQL):
- accounts (id, code, name, parent_id, level, type, dc_type, is_cash, aux_types, is_quantity, is_enabled)
- vouchers (id, voucher_no, date, period_id, attachments, status, creator_id, auditor_id, posted_at, source, deleted_at)
- voucher_entries (id, voucher_id, account_id, row_number, summary, debit_amount, credit_amount, quantity, price)
- entry_auxiliaries (id, entry_id, aux_type, department_id, individual_id, counterparty_id, project_id)
- departments (id, code, name, is_enabled)
- individuals (id, code, name, is_enabled)
- counterparties (id, code, name, is_enabled)
- projects (id, code, name, is_enabled)
- periods (id, year, month, status)
- account_balances (id, period_id, account_id, opening_debit, opening_credit, current_debit, current_credit, closing_debit, closing_credit)
- carry_forwards (id, period_id, template_id, voucher_id, from_account_id, to_account_id, amount)
- carry_templates (id, name, description, rules, sort_order, is_enabled)
- users (id, username, display_name, role_id, is_enabled)
- roles (id, name, permissions)
- audit_logs (id, user_id, action, resource_type, resource_id, created_at)
- cash_journals (id, date, period_id, voucher_id, account_id, summary, debit, credit, balance)
- bank_journals (id, date, period_id, voucher_id, account_id, summary, debit, credit, balance)
- fixed_assets (id, code, name, category, purchase_date, purchase_amount, salvage_value, useful_life_months, depreciation_method, monthly_depreciation, accumulated_depreciation, net_value, status, dept_id)
- refresh_tokens (id, user_id, token_hash, expires_at, revoked_at)

All monetary amounts are NUMERIC(18,2). All IDs are UUID.
voucher_entries.debit_amount and credit_amount are XOR (exactly one > 0 per row).
vouchers.deleted_at IS NULL means the voucher is active (not soft-deleted).
vouchers.status values: draft, audited, posted, reversed.
"""


async def execute_nl_query(
    question: str,
    conversation_id: _uuid.UUID | None,
    ai_db: AsyncSession,
) -> AIQueryResponse:
    """Execute a natural language query against the AI read-only database.

    Full security: ai_readonly DB, sqlparse SELECT check, forced LIMIT, 5s timeout.
    """
    # 1. Get schema info
    schema = get_db_schema_summary()

    # 2. Build prompt
    prompt = f"""You are a safe PostgreSQL query generator. Only generate SELECT statements.

Database Schema:
{schema}

Question: {question}

Instructions:
- Generate a single SELECT query that answers the question
- Use proper JOINs and aggregations as needed
- Use LIMIT in your query
- All UUID columns are stored as UUID type
- Use COALESCE for nullable sums
- Return JSON only, in this exact shape: {{"sql": "SELECT ..."}}
"""

    # 3. Call LLM. DeepSeek JSON mode returns a JSON object; keep a fallback
    # for providers or tests that still return a bare SQL string.
    raw_response = await invoke_structured(prompt)
    sql = extract_sql_from_llm_response(raw_response)

    # 4. Validate SQL (CRITICAL SECURITY)
    sql = validate_readonly_sql(sql)

    # 5. Execute on ai_readonly DB. LLM-generated SQL can always fail at
    # runtime (bad column, dialect mismatch, timeout) — surface a clean
    # AI error instead of an unhandled 500.
    start_time = time.monotonic()
    try:
        result = await ai_db.execute(text(sql))
    except SQLAlchemyError as e:
        # Leave the session clean — a failed statement otherwise poisons
        # the connection's transaction for subsequent requests.
        await ai_db.rollback()
        raise AIGenerationFailedError(
            f"生成的 SQL 执行失败: {type(e).__name__}"
        ) from e
    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    columns = list(result.keys())
    rows_data = [list(row) for row in result.fetchall()]

    return AIQueryResponse(
        conversation_id=conversation_id or _uuid.uuid4(),
        question=question,
        sql=sql,
        columns=columns,
        rows=rows_data,
        row_count=len(rows_data),
        execution_time_ms=elapsed_ms,
    )
