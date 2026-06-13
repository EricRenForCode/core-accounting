"""AI module — LLM client, voucher generator, NL query, report interpreter, period checker."""

from app.ai.llm_client import get_llm, get_llm_fallback, invoke_structured
from app.ai.voucher_generator import generate_voucher_from_description
from app.ai.nl_query import execute_nl_query, validate_readonly_sql, get_db_schema_summary
from app.ai.report_interpreter import interpret_report
from app.ai.period_checker import run_period_checks

__all__ = [
    "get_llm",
    "get_llm_fallback",
    "invoke_structured",
    "generate_voucher_from_description",
    "execute_nl_query",
    "validate_readonly_sql",
    "get_db_schema_summary",
    "interpret_report",
    "run_period_checks",
]
