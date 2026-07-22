"""Aliyun (Alibaba Cloud) OCR client — 混贴发票识别 (RecognizeMixedInvoices).

Wraps the official `alibabacloud_ocr_api20210707` SDK. Only invoked when
`ALIYUN_OCR_ACCESS_KEY_ID` / `ALIYUN_OCR_ACCESS_KEY_SECRET` are configured;
callers must treat `AliyunOcrError` as a signal to fall back to the
rule-based recognizer (see `app/ai/document_recognizer.py`).

The SDK call is synchronous (blocking network I/O) — callers running in an
async context should invoke `recognize_mixed_invoices` via `asyncio.to_thread`.
"""

import json
from io import BytesIO
from typing import Optional

from alibabacloud_ocr_api20210707 import models as ocr_models
from alibabacloud_ocr_api20210707.client import Client as OcrClient
from alibabacloud_tea_openapi import models as open_api_models

from app.config import Settings


class AliyunOcrError(Exception):
    """Raised when the Aliyun OCR call fails or returns unusable data."""


def is_configured(settings: Optional[Settings] = None) -> bool:
    """Whether Aliyun OCR credentials are set (feature flag)."""
    return (settings or Settings()).aliyun_ocr_configured


def _build_client(settings: Settings) -> OcrClient:
    config = open_api_models.Config(
        access_key_id=settings.ALIYUN_OCR_ACCESS_KEY_ID.get_secret_value(),
        access_key_secret=settings.ALIYUN_OCR_ACCESS_KEY_SECRET.get_secret_value(),
        endpoint=settings.ALIYUN_OCR_ENDPOINT,
    )
    return OcrClient(config)


def recognize_mixed_invoices(
    file_bytes: bytes, settings: Optional[Settings] = None
) -> dict:
    """Call RecognizeMixedInvoices (混贴发票识别) and return the parsed `Data`.

    Auto-detects invoice type (VAT invoice, taxi/train ticket, quota
    invoice, ...). Returns a dict shaped like:
    `{"count": int, "subMsgs": [{"type": str, "op": str, "result": {"data": {...}}}]}`.

    Raises `AliyunOcrError` on any auth/network/parse failure — never
    raises the underlying SDK exception so callers can fall back cleanly.
    """
    settings = settings or Settings()
    if not settings.aliyun_ocr_configured:
        raise AliyunOcrError("Aliyun OCR is not configured")

    client = _build_client(settings)
    request = ocr_models.RecognizeMixedInvoicesRequest(body=BytesIO(file_bytes))
    try:
        response = client.recognize_mixed_invoices(request)
    except Exception as exc:  # SDK raises TeaException/generic Exception
        raise AliyunOcrError(f"OCR request failed: {exc}") from exc

    body = response.body
    if body is None or not body.data:
        raise AliyunOcrError("OCR returned empty data")

    try:
        return json.loads(body.data)
    except (TypeError, ValueError) as exc:
        raise AliyunOcrError(f"Failed to parse OCR response: {exc}") from exc
