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
    """Generate voucher entries from natural language description (§7.3)."""
    from app.ai.voucher_generator import generate_voucher_from_description
    from app.models.period import Period

    # Validate the period exists BEFORE any LLM call (404 early, no tokens spent).
    period = await db.get(Period, body.period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    return await generate_voucher_from_description(
        description=body.description,
        period_id=body.period_id,
        db=db,
    )


@router.post("/voucher/refine", response_model=AIVoucherResponse)
async def refine_voucher(
    body: AIRefineRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ai:use")),
) -> AIVoucherResponse:
    """Refine a previously generated voucher based on user feedback."""
    from app.ai.voucher_generator import generate_voucher_from_description
    # Re-generate with refinement context appended
    description = f"(修正: {body.refinement}) (原始对话ID: {body.conversation_id})"
    # Use the most recent period as context
    from sqlalchemy import select
    from app.models.period import Period

    period_result = await db.execute(
        select(Period).order_by(Period.year.desc(), Period.month.desc()).limit(1)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="未找到会计期间")

    return await generate_voucher_from_description(
        description=description,
        period_id=period.id,
        db=db,
    )


@router.post("/reports/interpret", response_model=AIReportInterpretResponse)
async def interpret_report_route(
    body: AIReportInterpretRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ai:use")),
) -> AIReportInterpretResponse:
    """AI-powered financial report interpretation."""
    from app.ai.report_interpreter import interpret_report
    return await interpret_report(
        period_id=body.period_id,
        report_type=body.report_type,
        db=db,
    )


@router.post("/period/check", response_model=AIProceedCheckResponse)
async def period_check_route(
    period_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ai:use")),
) -> AIProceedCheckResponse:
    """Run AI-powered pre-close checks for an accounting period."""
    from app.ai.period_checker import run_period_checks
    return await run_period_checks(period_id=period_id, db=db)


@router.post("/query", response_model=AIQueryResponse)
async def nl_query_route(
    body: AIQueryRequest,
    ai_db: AsyncSession = Depends(get_ai_readonly_db),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ai:use")),
) -> AIQueryResponse:
    """Execute a natural language query against the database (§4 security)."""
    from app.ai.nl_query import execute_nl_query
    return await execute_nl_query(
        question=body.question,
        conversation_id=body.conversation_id,
        ai_db=ai_db,
    )


@router.post("/query/explain", response_model=AIExplainQueryResponse)
async def explain_query_route(
    body: AIExplainQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ai:use")),
) -> AIExplainQueryResponse:
    """Explain a generated SQL query in plain language."""
    from app.ai.llm_client import invoke_structured
    import json

    prompt = f"""请用简单的中文解释以下 SQL 查询的含义:

{body.sql}

返回 JSON 格式:
{{"explanation": "解释内容"}}
"""
    try:
        raw = await invoke_structured(prompt)
        parsed = json.loads(raw)
        return AIExplainQueryResponse(
            original_sql=body.sql,
            explanation=parsed.get("explanation", "无法解析此 SQL"),
        )
    except Exception:
        return AIExplainQueryResponse(
            original_sql=body.sql,
            explanation="无法解析此 SQL 查询",
        )
