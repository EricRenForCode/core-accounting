"""Unit tests for the OCR/AI document recognizer (§original-documents).

Covers: rule-engine fallback (default, no Aliyun OCR configured), the
Aliyun OCR → RecognitionResult mapping, and fallback-on-failure/no-match
behavior — without ever making a real network call.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from app.ai import document_recognizer as recognizer
from app.ai.aliyun_ocr import AliyunOcrError


def _vat_invoice_ocr_response(**overrides: str) -> dict:
    fields = {
        "invoiceNumber": "12345678",
        "invoiceDate": "2026年06月15日",
        "invoiceAmountPreTax": "500.00",
        "invoiceTax": "45.00",
        "totalAmount": "545.00",
        "sellerName": "携程商旅有限公司",
        **overrides,
    }
    return {
        "count": 1,
        "subMsgs": [
            {
                "type": "增值税电子普通发票",
                "op": "invoice",
                "index": 0,
                "result": {"data": {k: {"value": v} for k, v in fields.items()}},
            }
        ],
    }


# ── Default (no Aliyun OCR configured): rule-engine fallback ───

async def test_no_file_path_uses_rule_engine():
    result = await recognizer.recognize_document(
        "travel_差旅报销_2026-06-15_500.00.pdf", "application/pdf", 100
    )
    assert result.document_type == "reimbursement"
    assert result.amount == Decimal("500.00")
    assert result.issue_date.isoformat() == "2026-06-15"


async def test_ocr_not_configured_uses_rule_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(recognizer, "is_configured", lambda settings=None: False)
    file_path = tmp_path / "scan.jpg"
    file_path.write_bytes(b"fake image bytes")

    result = await recognizer.recognize_document(
        "rent_房租_3000.jpg", "image/jpeg", 100, file_path=file_path
    )
    assert result.document_type == "invoice"
    assert result.amount == Decimal("3000")


# ── Aliyun OCR path ─────────────────────────────────────────────

async def test_ocr_maps_vat_invoice(monkeypatch, tmp_path):
    monkeypatch.setattr(recognizer, "is_configured", lambda settings=None: True)
    monkeypatch.setattr(
        recognizer,
        "recognize_mixed_invoices",
        lambda file_bytes, settings=None: _vat_invoice_ocr_response(),
    )
    file_path = tmp_path / "invoice.jpg"
    file_path.write_bytes(b"fake image bytes")

    result = await recognizer.recognize_document(
        "invoice.jpg", "image/jpeg", 100, file_path=file_path
    )
    assert result.document_type == "invoice"
    assert result.amount == Decimal("500.00")
    assert result.tax_amount == Decimal("45.00")
    assert result.total_amount == Decimal("545.00")
    assert result.issue_date.isoformat() == "2026-06-15"
    assert result.invoice_no == "12345678"
    assert result.counterparty_name == "携程商旅有限公司"
    assert result.confidence >= Decimal("0.8")
    entries = result.suggested_entries
    assert len(entries) == 2
    # sellerName matches the 差旅 rule set → 6602 (kept as generic expense here
    # since "携程" doesn't hit a keyword, but the entry should still balance).
    assert entries[0].debit_amount == entries[1].credit_amount == Decimal("545.00")


async def test_ocr_maps_taxi_invoice_to_reimbursement(monkeypatch, tmp_path):
    monkeypatch.setattr(recognizer, "is_configured", lambda settings=None: True)
    ocr_response = {
        "count": 1,
        "subMsgs": [
            {
                "type": "出租车发票",
                "op": "taxi_invoice",
                "result": {
                    "data": {
                        "invoiceNumber": {"value": "99887766"},
                        "invoiceDate": {"value": "2026-06-20"},
                        "invoiceAmountPreTax": {"value": "88.00"},
                        "totalAmount": {"value": "88.00"},
                    }
                },
            }
        ],
    }
    monkeypatch.setattr(
        recognizer, "recognize_mixed_invoices", lambda file_bytes, settings=None: ocr_response
    )
    file_path = tmp_path / "taxi.png"
    file_path.write_bytes(b"fake image bytes")

    result = await recognizer.recognize_document(
        "taxi.png", "image/png", 100, file_path=file_path
    )
    assert result.document_type == "reimbursement"
    assert result.suggested_entries[0].account_code == "6602"
    assert result.amount == Decimal("88.00")


async def test_ocr_no_invoice_detected_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(recognizer, "is_configured", lambda settings=None: True)
    monkeypatch.setattr(
        recognizer,
        "recognize_mixed_invoices",
        lambda file_bytes, settings=None: {"count": 0, "subMsgs": []},
    )
    file_path = tmp_path / "travel_差旅_500.jpg"
    file_path.write_bytes(b"fake image bytes")

    result = await recognizer.recognize_document(
        "travel_差旅_500.jpg", "image/jpeg", 100, file_path=file_path
    )
    assert result.document_type == "reimbursement"  # rule-engine fallback kicked in
    assert any("兜底" in w for w in result.warnings)


async def test_ocr_error_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(recognizer, "is_configured", lambda settings=None: True)

    def _raise(file_bytes, settings=None):
        raise AliyunOcrError("network timeout")

    monkeypatch.setattr(recognizer, "recognize_mixed_invoices", _raise)
    file_path = tmp_path / "rent_房租_3000.jpg"
    file_path.write_bytes(b"fake image bytes")

    result = await recognizer.recognize_document(
        "rent_房租_3000.jpg", "image/jpeg", 100, file_path=file_path
    )
    assert result.document_type == "invoice"
    assert any("兜底" in w for w in result.warnings)


async def test_non_image_suffix_skips_ocr_even_if_configured(monkeypatch, tmp_path):
    monkeypatch.setattr(recognizer, "is_configured", lambda settings=None: True)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("OCR should not be called for non-image/pdf files")

    monkeypatch.setattr(recognizer, "recognize_mixed_invoices", _fail_if_called)
    file_path = tmp_path / "ledger.xlsx"
    file_path.write_bytes(b"fake xlsx bytes")

    result = await recognizer.recognize_document(
        "ledger.xlsx", "application/vnd.ms-excel", 100, file_path=file_path
    )
    assert result is not None
