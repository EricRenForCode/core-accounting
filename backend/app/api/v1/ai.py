"""AI feature routes (§3.12).

POST /ai/voucher/generate    — NL → voucher generation
POST /ai/voucher/refine      — refine/correct generated voucher
POST /ai/reports/interpret  — AI report interpretation
POST /ai/period/check       — period close pre-check
POST /ai/query              — NL → SQL query (ai_readonly, sqlparse, LIMIT enforced)
POST /ai/query/explain      — explain generated SQL

§4 Security for /ai/query:
- Uses dedicated ai_readonly database connection (SELECT only, statement_timeout=5s)
- sqlparse validation: only SELECT statements allowed
- Automatic LIMIT 1000 if not present
- Input max 500 chars
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_ai_readonly_db, get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.schemas.period import (
    AIExplainQueryRequest,
    AIExplainQueryResponse,
    AIProceedCheckResponse,
    AIQueryRequest,
    AIQueryResponse,
    AIReportInterpretRequest,
    AIReportInterpretResponse,
    AIRefineRequest,
    AIVoucherRequest,
    AIVoucherResponse,
)

router = APIRouter()


# ── NL → Voucher Generation ───────────────────────────────────


@router.post("/voucher/generate", response_model=AIVoucherResponse)
async def generate_voucher(
    body: AIVoucherRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ai:use")),
) -> AIVoucherResponse:
    """Generate voucher entries from natural language description.

    §7.3 Logic:
    1. Retrieve context: leaf accounts (enabled, no children) + top-50 frequent accounts
    2. Retrieve all auxiliary archives (small data)
    3. Build compressed prompt with account list + description
    4. Call LLM (LangChain ChatOpenAI, structured JSON output)
    5. Parse LLM response, validate account_ids exist in context
    6. Check debit/credit balance; if unbalanced, retry with fix prompt (max 1 retry)
    7. Save conversation record (ai_conversation JSONB)
    8. Return AIVoucherResponse with entries, balance status, matched accounts
    """
    raise NotImplementedError(
        "generate_voucher — §7.3:\n"
        "1. leaf_accounts = SELECT accounts WHERE is_enabled AND NOT EXISTS (SELECT 1 FROM accounts children WHERE children.parent_id=accounts.id)\n"
        "2. frequent_accounts = top 50 by usage count in this period\n"
        "3. accounts = dedupe(leaf_accounts + frequent_accounts)\n"
        "4. aux_entities = SELECT all departments, individuals, counterparties, projects\n"
        "5. prompt = build_compressed_prompt(description, accounts, aux_entities)\n"
        "6. llm_response = await llm.ainvoke(prompt, response_format='json_object')\n"
        "7. Validate: all account_ids exist; invalid → raise AI_INVALID_RESPONSE\n"
        "8. Check balance: sum(debit) == sum(credit)\n"
        "9. If unbalanced: fix_prompt, retry once\n"
        "10. conversation_id = uuid4(); save to DB\n"
        "11. Return AIVoucherResponse"
    )


@router.post("/voucher/refine", response_model=AIVoucherResponse)
async def refine_voucher(
    body: AIRefineRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ai:use")),
) -> AIVoucherResponse:
    """Refine a previously generated voucher based on user feedback.

    Loads the conversation history and applies the user's refinement.
    """
    raise NotImplementedError(
        "refine_voucher:\n"
        "1. Load conversation by conversation_id\n"
        "2. Append refinement to conversation\n"
        "3. Call LLM with full conversation + refinement\n"
        "4. Same validation as generate_voucher\n"
        "5. Return updated AIVoucherResponse"
    )


# ── AI Report Interpretation ──────────────────────────────────


@router.post("/reports/interpret", response_model=AIReportInterpretResponse)
async def interpret_report(
    body: AIReportInterpretRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ai:use")),
) -> AIReportInterpretResponse:
    """AI-powered financial report interpretation.

    Analyzes balance sheet, income statement, or cash flow statement
    and returns highlights, warnings, and natural language interpretation.
    """
    raise NotImplementedError(
        "interpret_report:\n"
        "1. Generate the requested report data\n"
        "2. Compare with prior period (YoY/MoM)\n"
        "3. Call LLM with report data + comparison\n"
        "4. Extract highlights and warnings\n"
        "5. Return AIReportInterpretResponse"
    )


# ── AI Period Check ───────────────────────────────────────────


@router.post("/period/check", response_model=AIProceedCheckResponse)
async def period_check(
    period_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ai:use")),
) -> AIProceedCheckResponse:
    """Run AI-powered pre-close checks for an accounting period.

    Checks 10 items (same as GET /carry-forward/check).
    If period has known issues, may trigger LLM analysis.
    """
    raise NotImplementedError(
        "period_check:\n"
        "1. Run 10 standard checks (same as carry-forward/check)\n"
        "2. For anomalies (warn/fail), call LLM for deeper analysis\n"
        "3. Return AIProceedCheckResponse"
    )


# ── NL → SQL Query (with security measures) ───────────────────


@router.post("/query", response_model=AIQueryResponse)
async def nl_query(
    body: AIQueryRequest,
    ai_db: AsyncSession = Depends(get_ai_readonly_db),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ai:use")),
) -> AIQueryResponse:
    """Execute a natural language query against the database.

    §4 Security measures:
    - Uses ai_readonly DB connection (SELECT only, statement_timeout=5s)
    - sqlparse validation: only SELECT statements allowed → 403 AI_READONLY_VIOLATION otherwise
    - Auto-appends LIMIT 1000 if no LIMIT clause present
    - Input max 500 chars (enforced by AIQueryRequest schema)

    Logic:
    1. Get DB schema info (table list, column comments) for prompt context
    2. If conversation_id provided: load prior context
    3. Build prompt: schema + question + instructions for safe SQL generation
    4. Call LLM to generate SQL
    5. Validate SQL with sqlparse (SELECT only)
    6. Force LIMIT if missing
    7. Execute SQL on ai_readonly connection
    8. Measure execution time
    9. Return AIQueryResponse with SQL, columns, rows, timing
    """
    raise NotImplementedError(
        "nl_query:\n"
        "1. schema_info = get_db_schema_summary()  # table names + column comments, no data\n"
        "2. context = load_conversation(conversation_id) if provided\n"
        "3. prompt = f'''You are a safe SQL generator. Schema:\\n{schema_info}\\n\\nQuestion: {body.question}\\n\\nReturn ONLY valid PostgreSQL SELECT. No DML/DDL.'''\n"
        "4. sql = await llm.ainvoke(prompt)  # extract SQL from response\n"
        "5. validate_readonly_sql(sql):\n"
        "     import sqlparse\n"
        "     statements = sqlparse.parse(sql)\n"
        "     for stmt in statements:\n"
        "         if stmt.get_type() != 'SELECT':\n"
        "             raise HTTPException(403, detail={'code': 'AI_READONLY_VIOLATION', ...})\n"
        "     if 'LIMIT' not in sql.upper():\n"
        "         sql += ' LIMIT 1000'\n"
        "6. result = await ai_db.execute(text(sql))\n"
        "7. columns = list(result.keys())\n"
        "8. rows = [list(row) for row in result.fetchall()]\n"
        "9. Save conversation\n"
        "10. Return AIQueryResponse(sql=sql, columns=columns, rows=rows, ...)"
    )


# ── SQL Explanation ───────────────────────────────────────────


@router.post("/query/explain", response_model=AIExplainQueryResponse)
async def explain_query(
    body: AIExplainQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ai:use")),
) -> AIExplainQueryResponse:
    """Explain a generated SQL query in plain language.

    Takes a SQL string and returns a natural language explanation.
    """
    raise NotImplementedError(
        "explain_query:\n"
        "1. Call LLM with prompt: 'Explain this SQL query in simple terms: {sql}'\n"
        "2. Return natural language explanation"
    )
