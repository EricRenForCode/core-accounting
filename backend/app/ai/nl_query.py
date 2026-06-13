"""AI Natural Language → SQL Query with security measures (§4, §3.12).

Core security:
- Uses ai_readonly PostgreSQL connection (SELECT only, no DML/DDL)
- sqlparse validation rejects non-SELECT statements
- Forces LIMIT 1000 if missing
- Statement timeout: 5 seconds
- Input max 500 characters
"""

from uuid import UUID

import sqlparse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ReadOnlyViolationError
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
    # Parse SQL into statements
    parsed = sqlparse.parse(sql)

    for stmt in parsed:
        if stmt.get_type() != "SELECT":
            raise ReadOnlyViolationError(stmt.get_type())

    # Force LIMIT if not present (case-insensitive check)
    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(";").rstrip() + " LIMIT 1000"

    return sql


def get_db_schema_summary() -> str:
    """Build a concise schema summary for the LLM prompt.

    Returns a description of tables and columns without exposing data.
    """
    # Static schema reference — avoids querying system catalogs at runtime
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
    conversation_id: UUID | None,
    ai_db: AsyncSession,
) -> AIQueryResponse:
    """Execute a natural language query against the AI read-only database.

    Full Logic:
    ───────────

    1. GET SCHEMA INFO:
       schema = get_db_schema_summary()  # static reference, no DB call needed

    2. LOAD CONVERSATION CONTEXT:
       If conversation_id is provided, load prior questions + SQL from storage
       to provide context for follow-up queries.

    3. BUILD PROMPT:
       System: "You are a safe PostgreSQL query generator. Only generate SELECT statements.
                Schema: {schema}. Respond ONLY with the SQL query, no explanation."
       User: question (with conversation context if applicable)

    4. CALL LLM:
       sql = await llm.ainvoke(prompt)
       Extract SQL from response (strip markdown code fences if present)

    5. VALIDATE SQL (CRITICAL SECURITY):
       sql = validate_readonly_sql(sql)
       → sqlparse.parse() checks statement type
       → Only SELECT allowed; DML/DDL → 403 ReadOnlyViolationError
       → Auto-appends LIMIT 1000 if missing

    6. EXECUTE ON AI_READONLY DB:
       The ai_readonly connection has:
       - statement_timeout = 5000 (5 seconds, set at connection level)
       - default_transaction_read_only = on
       → Prevents any write operations at the PostgreSQL level

       start_time = time.monotonic()
       result = await ai_db.execute(text(sql))
       columns = list(result.keys())
       rows = [list(row) for row in result.fetchall()]
       elapsed_ms = int((time.monotonic() - start_time) * 1000)

    7. SAVE CONVERSATION:
       Store (question, sql, row_count, timestamp) for conversation history

    8. RETURN:
       AIQueryResponse(
           conversation_id=conversation_id or new_uuid,
           question=question,
           sql=sql,
           columns=columns,
           rows=rows,
           row_count=len(rows),
           execution_time_ms=elapsed_ms,
       )
    """
    raise NotImplementedError(
        "execute_nl_query — see docstring for full §4 + §3.12 logic"
    )
