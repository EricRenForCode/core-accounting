"""Original document (原始凭证) request/response schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OriginalDocumentResponse(BaseModel):
    """Original document detail response."""

    id: UUID
    file_name: str
    content_type: str
    file_size: int
    document_type: str
    status: str
    issue_date: Optional[date] = None
    amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    counterparty_name: Optional[str] = None
    invoice_no: Optional[str] = None
    summary: Optional[str] = None
    recognized_fields: Optional[dict] = None
    recognition_confidence: Optional[Decimal] = None
    voucher_id: Optional[UUID] = None
    voucher_no: Optional[str] = None
    uploader_id: UUID
    uploader_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UpdateOriginalDocumentRequest(BaseModel):
    """PUT /original-documents/{id} — 人工校对识别字段."""

    document_type: Optional[str] = None
    issue_date: Optional[date] = None
    amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2, max_digits=18)
    tax_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2, max_digits=18)
    total_amount: Optional[Decimal] = Field(
        None, ge=0, decimal_places=2, max_digits=18
    )
    counterparty_name: Optional[str] = Field(None, max_length=200)
    invoice_no: Optional[str] = Field(None, max_length=100)
    summary: Optional[str] = Field(None, max_length=200)
    recognized_fields: Optional[dict] = None


class LinkVoucherRequest(BaseModel):
    """POST /original-documents/{id}/link-voucher body."""

    voucher_id: UUID


class OriginalDocumentListParams(BaseModel):
    """GET /original-documents query params."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: Optional[str] = None
    document_type: Optional[str] = None
    keyword: Optional[str] = Field(default=None, max_length=100)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    voucher_id: Optional[UUID] = None
