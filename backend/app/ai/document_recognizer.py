"""Document recognizer — OCR/AI 识别原始凭证 (§original-documents).

`recognize_document` calls Aliyun OCR (混贴发票识别, `app/ai/aliyun_ocr.py`)
when `ALIYUN_OCR_ACCESS_KEY_ID/SECRET` are configured and the file is an
image/PDF; otherwise — and whenever Aliyun OCR fails or detects no invoice —
it falls back to deterministic filename/keyword rules (`_recognize_by_rules`).
AI/OCR output NEVER posts directly — it only prefills a voucher draft that a
human confirms and audits.
"""

import asyncio
import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.ai.aliyun_ocr import AliyunOcrError, is_configured, recognize_mixed_invoices
from app.config import Settings

logger = logging.getLogger(__name__)


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


def _recognize_by_rules(
    file_name: str,
    content_type: str,
    file_size: int,
) -> RecognitionResult:
    """Deterministic filename/keyword fallback recognizer (no real OCR).

    Used when Aliyun OCR is not configured, not applicable to this file
    type, or fails/returns no structured invoice data.
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


# ── Aliyun OCR mapping (混贴发票识别 → RecognitionResult) ──────

_OCR_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".pdf"}

# Aliyun invoice `op` → (document_type, debit account). None means "guess
# from the recognized text via _EXPENSE_RULES" (generic VAT invoices cover
# many expense categories, so they can't be mapped from `op` alone).
_INVOICE_OP_MAP: dict[str, tuple[str, Optional[str]]] = {
    "taxi_invoice": ("reimbursement", "6602"),
    "train_invoice": ("reimbursement", "6602"),
    "air_itinerary": ("reimbursement", "6602"),
    "bus_ship_ticket": ("reimbursement", "6602"),
    "roll_ticket": ("reimbursement", "6602"),
    "toll_invoice": ("reimbursement", "6602"),
    "quota_invoice": ("invoice", "6602"),
}

_OCR_DATE_RE = re.compile(r"(20\d{2})[-/年.]?(\d{1,2})[-/月.]?(\d{1,2})日?")


def _field_value(data: dict, key: str) -> Optional[str]:
    """Extract a field's text value from an OCR result dict.

    Aliyun OCR fields are usually `{"value": ..., "keyProb": ..., ...}`,
    but fall back to a plain scalar if the SDK ever returns one directly.
    """
    raw = data.get(key)
    if isinstance(raw, dict):
        raw = raw.get("value")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _ocr_amount(data: dict, key: str) -> Optional[Decimal]:
    text = _field_value(data, key)
    if not text:
        return None
    try:
        return Decimal(text.replace(",", "").replace("￥", "").replace("¥", ""))
    except InvalidOperation:
        return None


def _ocr_date(data: dict, key: str) -> Optional[date]:
    text = _field_value(data, key)
    if not text:
        return None
    m = _OCR_DATE_RE.search(text)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _map_aliyun_invoice(ocr_data: dict) -> Optional[RecognitionResult]:
    """Map a `RecognizeMixedInvoices` response into a `RecognitionResult`.

    Returns None if no invoice was detected (`count` == 0 or empty
    `subMsgs`) — caller should fall back to the rule-based recognizer.
    """
    sub_msgs = ocr_data.get("subMsgs") or []
    if not sub_msgs:
        return None
    sub = sub_msgs[0]
    op = str(sub.get("op") or "").strip()
    type_label = str(sub.get("type") or "票据").strip()

    result = sub.get("result")
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, dict):
        data = result if isinstance(result, dict) else {}

    amount = _ocr_amount(data, "invoiceAmountPreTax")
    tax_amount = _ocr_amount(data, "invoiceTax")
    total_amount = _ocr_amount(data, "totalAmount") or amount
    issue_date = _ocr_date(data, "invoiceDate") or _ocr_date(data, "date")
    invoice_no = _field_value(data, "invoiceNumber") or _field_value(data, "invoiceCode")
    counterparty = _field_value(data, "sellerName")

    warnings: list[str] = []
    if amount is None and total_amount is None:
        warnings.append("未能从票据中识别金额，请人工填写")
    if issue_date is None:
        warnings.append("未能从票据中识别日期，请人工填写")

    mapped = _INVOICE_OP_MAP.get(op)
    if mapped is not None:
        doc_type, debit_code = mapped
    else:
        doc_type = "invoice"
        debit_code = None
        keyword_source = f"{counterparty or ''} {type_label}".lower()
        for keywords, _dtype, code, _label in _EXPENSE_RULES:
            if any(k in keyword_source for k in keywords):
                debit_code = code
                break
        debit_code = debit_code or "6602"  # 管理费用: generic expense fallback

    summary = f"取得{type_label}" + (f"（{counterparty}）" if counterparty else "")
    entry_amount = total_amount or amount or Decimal("0")
    entries = [
        SuggestedEntry(account_code=debit_code, summary=summary, debit_amount=entry_amount),
        SuggestedEntry(account_code="1001", summary=summary, credit_amount=entry_amount),
    ]

    confidence = Decimal("0.9") if (amount or total_amount) and issue_date else Decimal("0.6")

    return RecognitionResult(
        document_type=doc_type,
        issue_date=issue_date,
        amount=amount,
        tax_amount=tax_amount,
        total_amount=total_amount,
        counterparty_name=counterparty,
        invoice_no=invoice_no,
        summary=summary,
        suggested_entries=entries,
        confidence=confidence,
        warnings=warnings,
    )


async def recognize_document(
    file_name: str,
    content_type: str,
    file_size: int,
    file_path: Optional[Path] = None,
) -> RecognitionResult:
    """Recognize an original document and suggest voucher entries.

    Calls Aliyun OCR (real image/PDF recognition) when configured and
    `file_path` is given; falls back to the deterministic rule engine when
    OCR is unconfigured, not applicable, fails, or detects nothing.
    """
    settings = Settings()
    suffix = Path(file_name).suffix.lower()
    can_use_ocr = (
        is_configured(settings)
        and file_path is not None
        and suffix in _OCR_IMAGE_SUFFIXES
    )

    if can_use_ocr:
        assert file_path is not None
        try:
            file_bytes = await asyncio.to_thread(file_path.read_bytes)
            ocr_data = await asyncio.to_thread(
                recognize_mixed_invoices, file_bytes, settings
            )
            result = _map_aliyun_invoice(ocr_data)
            if result is not None:
                return result
            logger.info("Aliyun OCR detected no invoice for %s, falling back", file_name)
        except AliyunOcrError as exc:
            logger.warning("Aliyun OCR failed for %s: %s", file_name, exc)

        fallback = _recognize_by_rules(file_name, content_type, file_size)
        fallback.warnings.append("阿里云OCR未识别到票据信息，已使用规则引擎兜底，请人工核对")
        return fallback

    return _recognize_by_rules(file_name, content_type, file_size)
