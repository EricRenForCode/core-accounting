"""AI Report Interpreter stub — analyzes financial statements and returns insights."""

from uuid import UUID

from app.schemas.period import AIReportInterpretResponse


async def interpret_report(
    period_id: UUID,
    report_type: str,
) -> AIReportInterpretResponse:
    """Interpret a financial report (balance sheet, income, cash flow) using AI.

    Logic:
    ──────

    1. GENERATE REPORT DATA:
       - Call the appropriate report generation function
       - Get comparison data from prior period (MoM or YoY)

    2. BUILD ANALYSIS PROMPT:
       - Include current period report data
       - Include prior period comparison (absolute and percentage changes)
       - System prompt: "You are a financial analyst. Analyze this report.
         Highlight key changes, identify risks, suggest areas for review."

    3. CALL LLM:
       response = await llm.ainvoke(prompt)

    4. EXTRACT STRUCTURED OUTPUT:
       - interpretation: Full natural language analysis
       - highlights: 3-5 positive findings
       - warnings: 2-3 risk areas or unusual patterns

    5. RETURN:
       AIReportInterpretResponse(
           period_id=period_id,
           report_type=report_type,
           interpretation="...",
           highlights=[...],
           warnings=[...],
       )
    """
    raise NotImplementedError("interpret_report — see docstring above")
