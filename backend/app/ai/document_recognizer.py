"""Document recognizer — OCR/AI 识别原始凭证 (§original-documents).

MVP implementation: deterministic filename/keyword rules that produce the
same structured output a real OCR + LLM pipeline would. Swap in a real
engine by replacing `recognize_document` (interface is stable: file path +
metadata in, `RecognitionResult` out). AI/OCR output NEVER posts directly —
it only prefills a voucher draft that a human confirms and audits.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from pydantic import BaseModel, Field


class SuggestedEntry(BaseModel):
    """One suggested voucher entry line derived from the document."""

    account_code: str
    summary: str
    debit_amount: Decimal = Decimal("0")
    credit_amount: Decimal = Decimal("0")
    aux_type: Optional[str] = None
    aux_name: Optional[str] = None


class RecognitionResult(BaseModel):
    """Structured recognition output for an original document."""

    document_type: str = "other"
    issue_date: Optional[date] = None
    amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    counterparty_name: Optional[str] = None
    invoice_no: Optional[str] = None
    summary: str = ""
    suggested_entries: list[SuggestedEntry] = Field(default_factory=list)
    confidence: Decimal = Decimal("0.5")
    warnings: list[str] = Field(default_factory=list)


# Keyword → (document_type, debit account, summary label). Bank receipts
# are handled separately (credit side differs).
_EXPENSE_RULES: list[tuple[tuple[str, ...], str, str, str]] = [
    (("travel", "差旅", "机票", "高铁", "出差"), "reimbursement", "6602", "报销差旅费"),
    (("rent", "房租", "租金"), "invoice", "6602", "支付房租"),
    (("payroll", "工资", "薪酬"), "payroll", "6602", "发放工资"),
    (("office", "办公"), "invoice", "6602", "购买办公用品"),
]

_AMOUNT_RE = re.compile(r"(\d+(?:\.\d{1,2})?)")
_DATE_RE = re.compile(r"(20\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])")


def _extract_amount(file_name: str) -> Optional[Decimal]:
    """Best-effort amount extraction from the file name (mock OCR)."""
    candidates = _AMOUNT_RE.findall(file_name)
    # Skip 8-digit date-like numbers; take the last remaining number.
    values = [c for c in candidates if not (len(c) == 8 and c.startswith("20"))]
    if not values:
        return None
    try:
        amount = Decimal(values[-1])
    except InvalidOperation:
        return None
    return amount if amount > 0 else None


def _extract_date(file_name: str) -> Optional[date]:
    """Best-effort issue-date extraction from the file name (mock OCR)."""
    m = _DATE_RE.search(file_name)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def recognize_document(
    file_name: str,
    content_type: str,
    file_size: int,
) -> RecognitionResult:
    """Recognize an original document and suggest voucher entries.

    MVP: rule-based on the file name. A real implementation would OCR the
    file at its storage path and run LLM structuring — the return type and
    call site stay unchanged.
    """
    lower = file_name.lower()
    warnings: list[str] = []
    amount = _extract_amount(file_name)
    issue_date = _extract_date(file_name)

    if amount is None:
        warnings.append("未能识别金额，请人工填写")
    if issue_date is None:
        warnings.append("未能识别票据日期，请人工填写")

    doc_type = "other"
    debit_code: Optional[str] = None
    credit_code = "1001"  # default: 库存现金
    summary = "原始凭证入账"

    for keywords, dtype, code, label in _EXPENSE_RULES:
        if any(k in lower for k in keywords):
            doc_type, debit_code, summary = dtype, code, label
            break

    if debit_code is None:
        if any(k in lower for k in ("bank", "回单", "转账")):
            # 银行回单：默认银行收款（借银行存款，贷其他应付款占位）
            doc_type, debit_code, credit_code = "bank_receipt", "1002", "2202"
            summary = "银行回单入账"
        elif any(k in lower for k in ("invoice", "发票", "fapiao")):
            doc_type, debit_code, summary = "invoice", "6602", "取得发票"
        elif any(k in lower for k in ("contract", "合同")):
            doc_type = "contract"
            warnings.append("合同类文件无法直接建议分录")
        else:
            warnings.append("未匹配到票据类型规则，请人工校对")

    entries: list[SuggestedEntry] = []
    if debit_code is not None:
        entry_amount = amount or Decimal("0")
        entries = [
            SuggestedEntry(
                account_code=debit_code,
                summary=summary,
                debit_amount=entry_amount,
            ),
            SuggestedEntry(
                account_code=credit_code,
                summary=summary,
                credit_amount=entry_amount,
            ),
        ]

    confidence = Decimal("0.85") if debit_code and amount else Decimal("0.5")

    return RecognitionResult(
        document_type=doc_type,
        issue_date=issue_date,
        amount=amount,
        total_amount=amount,
        summary=summary,
        suggested_entries=entries,
        confidence=confidence,
        warnings=warnings,
    )
