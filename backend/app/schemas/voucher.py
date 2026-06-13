"""Voucher request/response schemas (§3.3, §3.4)."""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator
from uuid import UUID


# ── Entry Schemas ─────────────────────────────────────────────


class AuxiliaryRef(BaseModel):
    """Auxiliary核算 reference within a voucher entry."""

    aux_type: str = Field(..., description="部门/个人/单位/项目")
    department_id: Optional[UUID] = None
    individual_id: Optional[UUID] = None
    counterparty_id: Optional[UUID] = None
    project_id: Optional[UUID] = None

    @model_validator(mode="after")
    def exactly_one_aux(self):
        count = sum(
            1 for v in [
                self.department_id,
                self.individual_id,
                self.counterparty_id,
                self.project_id,
            ] if v is not None
        )
        if count != 1:
            raise ValueError("Exactly one auxiliary entity reference required")
        return self


class VoucherEntrySchema(BaseModel):
    """Voucher entry request/response."""

    row_number: int = Field(..., ge=1)
    account_id: UUID
    summary: str = Field(..., min_length=1, max_length=200)
    debit_amount: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2, max_digits=18)
    credit_amount: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2, max_digits=18)
    quantity: Optional[Decimal] = Field(None, ge=0, decimal_places=4, max_digits=18)
    price: Optional[Decimal] = Field(None, ge=0, decimal_places=4, max_digits=18)
    auxiliaries: List[AuxiliaryRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def xor_debit_credit(self):
        """CHECK: (debit = 0 XOR credit = 0) and (debit > 0 OR credit > 0)."""
        d = self.debit_amount or Decimal("0")
        c = self.credit_amount or Decimal("0")
        if d == 0 and c == 0:
            raise ValueError("Entry must have either debit or credit > 0")
        if d > 0 and c > 0:
            raise ValueError("Entry cannot have both debit and credit > 0 (XOR)")
        return self


class VoucherEntryResponse(BaseModel):
    """Voucher entry in API responses."""

    id: UUID
    row_number: int
    account_id: UUID
    account: Optional[dict] = None  # {id, code, name}
    summary: str
    debit_amount: Decimal
    credit_amount: Decimal
    quantity: Optional[Decimal] = None
    price: Optional[Decimal] = None
    auxiliaries: List[dict] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ── Voucher Schemas ───────────────────────────────────────────


class CreateVoucherRequest(BaseModel):
    """POST /vouchers request body (§3.3)."""

    date: date
    period_id: UUID
    attachments: int = Field(default=0, ge=0)
    entries: List[VoucherEntrySchema] = Field(..., min_length=2)

    @model_validator(mode="after")
    def balanced(self):
        """Ensure total debit == total credit."""
        total_d = sum((e.debit_amount or Decimal("0")) for e in self.entries)
        total_c = sum((e.credit_amount or Decimal("0")) for e in self.entries)
        if total_d != total_c:
            raise ValueError(
                f"Unbalanced voucher: debit={total_d}, credit={total_c}"
            )
        return self


class UpdateVoucherRequest(BaseModel):
    """PUT /vouchers/{id} request body — only draft vouchers."""

    date: Optional[date] = None
    attachments: Optional[int] = Field(None, ge=0)
    entries: Optional[List[VoucherEntrySchema]] = None


class VoucherResponse(BaseModel):
    """Voucher detail response."""

    id: UUID
    voucher_no: str
    date: date
    period_id: UUID
    attachments: int
    status: str
    creator_id: UUID
    auditor_id: Optional[UUID] = None
    posted_at: Optional[datetime] = None
    source: str
    reversed_voucher_id: Optional[UUID] = None
    reversal_type: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    entries: List[VoucherEntryResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class VoucherListParams(BaseModel):
    """Query params for GET /vouchers."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort: str = Field(default="date")
    order: str = Field(default="desc", pattern="^(asc|desc)$")
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    status: Optional[str] = None
    keyword: Optional[str] = None
    period_id: Optional[UUID] = None


class ImportVoucherRequest(BaseModel):
    """POST /vouchers/import — Excel file upload (handled via Form)."""

    period_id: UUID
    override_existing: bool = False


class ExportVoucherRequest(BaseModel):
    """GET /vouchers/export query params."""

    format: str = Field(default="excel", pattern="^(excel|pdf)$")
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    status: Optional[str] = None
    keyword: Optional[str] = None
    period_id: Optional[UUID] = None


# ── Voucher Template Schemas (§3.4) ───────────────────────────


class TemplateEntry(BaseModel):
    """Pre-defined entry line in a template."""

    account_id: UUID
    summary: str = Field(default="")
    dc_side: str = Field(..., pattern="^(debit|credit)$")  # debit or credit
    auxiliaries: List[AuxiliaryRef] = Field(default_factory=list)


class CreateTemplateRequest(BaseModel):
    """POST /voucher-templates request body."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    entries: List[TemplateEntry] = Field(default_factory=list)
    is_enabled: bool = True


class UpdateTemplateRequest(BaseModel):
    """PUT /voucher-templates/{id} request body."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    entries: Optional[List[TemplateEntry]] = None
    is_enabled: Optional[bool] = None


class VoucherTemplateResponse(BaseModel):
    """Template API response."""

    id: UUID
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    entries: List[dict]
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
