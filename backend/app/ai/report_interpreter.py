"""AI Report Interpreter — analyzes financial statements and returns insights (§3.12)."""

import json

from app.ai.llm_client import invoke_structured
from app.schemas.period import AIReportInterpretResponse


async def interpret_report(
    period_id,
    report_type: str,
    db,
) -> AIReportInterpretResponse:
    """Interpret a financial report (balance sheet, income, cash flow) using AI.

    Args:
        period_id: Period UUID.
        report_type: One of balance_sheet/income/cash_flow/trial_balance.
        db: AsyncSession for fetching report data.
    """
    if db is None:
        raise ValueError("db session is required")

    # 1. Generate report data using existing report endpoints
    if report_type == "balance_sheet":
        from app.api.v1.reports import balance_sheet
        report_data = await balance_sheet(period_id=period_id, db=db)
        title = "资产负债表"
    elif report_type == "income":
        from app.api.v1.reports import income_statement
        report_data = await income_statement(period_id=period_id, db=db)
        title = "利润表"
    elif report_type == "cash_flow":
        from app.api.v1.reports import cash_flow
        report_data = await cash_flow(period_id=period_id, db=db)
        title = "现金流量表"
    else:
        title = "科目余额表"
        from app.api.v1.reports import trial_balance
        report_data = await trial_balance(period_id=period_id, db=db)

    # 2. Build analysis prompt with report data
    #    mode="json" makes Decimal/date/UUID values JSON-safe (report NUMERIC
    #    fields come back as Decimal, which json.dumps cannot serialize).
    report_json = json.dumps(
        report_data.model_dump(mode="json")
        if hasattr(report_data, "model_dump")
        else str(report_data),
        ensure_ascii=False,
        indent=2,
    )[:6000]  # Truncate for prompt size limit

    prompt = f"""你是一位资深财务分析师。请分析以下{title}数据。

期间: {report_data.period}

报表数据:
{report_json}

请提供:
1. 整体状况解读 (interpretation) — 2-3句话概括
2. 关键亮点 (highlights) — 3-5个正面发现
3. 风险提示 (warnings) — 2-3个需要关注的问题

请返回严格的 JSON 格式:
{{
  "interpretation": "总体分析...",
  "highlights": ["亮点1", "亮点2"],
  "warnings": ["风险1", "风险2"]
}}
"""

    # 3. Call LLM
    raw_response = await invoke_structured(prompt)

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        return AIReportInterpretResponse(
            period_id=str(period_id),
            report_type=report_type,
            interpretation="暂无法生成 AI 解读，请检查 LLM 配置。",
            highlights=[],
            warnings=[],
        )

    return AIReportInterpretResponse(
        period_id=str(period_id),
        report_type=report_type,
        interpretation=parsed.get("interpretation", ""),
        highlights=parsed.get("highlights", []),
        warnings=parsed.get("warnings", []),
    )
