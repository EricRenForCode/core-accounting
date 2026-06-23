"""Cashier and Asset schemas (§3.10, §3.11)."""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID


# ── Cash Journal (§3.10) ──────────────────────────────────────


class CashJournalRow(BaseModel):
    """Row in cash journal."""

    id: UUID
    date: date
    voucher_id: UUID
    voucher_no: Optional[str] = None
    account_id: UUID
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    summary: str
    debit: Decimal
    credit: Decimal
    balance: Decimal
    serial_no: Optional[str] = None
    counterparty: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CashJournalCreate(BaseModel):
    """Create a cash journal entry."""

    date: date
    account_id: UUID
    summary: str = Field(..., min_length=1, max_length=200)
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    counterparty: Optional[str] = None


class CashJournalResponse(BaseModel):
    """GET /cash-journals response."""

    account: dict
    period: dict
    opening_balance: Decimal = Decimal("0")
    rows: List[CashJournalRow]
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal = Decimal("0")


# ── Bank Journal (§3.10) ──────────────────────────────────────


class BankJournalRow(BaseModel):
    """Row in bank journal."""

    id: UUID
    date: date
    voucher_id: UUID
    voucher_no: Optional[str] = None
    account_id: UUID
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    summary: str
    debit: Decimal
    credit: Decimal
    balance: Decimal
    serial_no: Optional[str] = None
    counterparty: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BankJournalCreate(BaseModel):
    """Create a bank journal entry."""

    date: date
    account_id: UUID
    summary: str = Field(..., min_length=1, max_length=200)
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    counterparty: Optional[str] = None


class BankJournalImportRow(BaseModel):
    """Single row in bank statement import."""
    date: date
    summary: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    counterparty: Optional[str] = None
    serial_no: Optional[str] = None


class BankJournalImportRequest(BaseModel):
    """POST /bank-journals/import request body."""
    account_id: UUID
    period_id: UUID
    rows: List[BankJournalImportRow]


class BankJournalImportResponse(BaseModel):
    """Import result."""
    imported: int
    errors: List[dict] = Field(default_factory=list)


class BankJournalResponse(BaseModel):
    """GET /bank-journals response."""

    account: dict
    period: dict
    rows: List[BankJournalRow]
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal = Decimal("0")


# ── Bank Reconciliation (§3.10) ───────────────────────────────


class BankReconcileRequest(BaseModel):
    """POST /bank-reconcile request."""
    account_id: UUID
    period_id: UUID


class BankReconcileMatch(BaseModel):
    """A matched pair in reconciliation."""
    bank_entry_id: Optional[UUID] = None
    voucher_entry_id: Optional[UUID] = None
    date: date
    amount: Decimal
    description: str


class BankReconcileResponse(BaseModel):
    """POST /bank-reconcile response."""

    matched: List[BankReconcileMatch] = Field(default_factory=list)
    bank_only: List[dict] = Field(default_factory=list)   # 银行已记企业未记
    voucher_only: List[dict] = Field(default_factory=list) # 企业已记银行未记
    bank_balance: Decimal = Decimal("0")
    voucher_balance: Decimal = Decimal("0")
    reconciled_balance: Decimal = Decimal("0")


# ── Fixed Assets (§3.11) ──────────────────────────────────────


class FixedAssetCreate(BaseModel):
    """Create a fixed asset card."""
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=50)
    purchase_date: date
    purchase_amount: Decimal = Field(..., gt=0)
    salvage_value: Decimal = Decimal("0")
    useful_life_months: int = Field(..., gt=0)
    depreciation_method: str = Field(default="straight", pattern="^(straight|double_declining|sum_of_years)$")
    dept_id: Optional[UUID] = None


class FixedAssetUpdate(BaseModel):
    """Update a fixed asset card."""
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    purchase_amount: Optional[Decimal] = Field(None, gt=0)
    salvage_value: Optional[Decimal] = None
    useful_life_months: Optional[int] = Field(None, gt=0)
    depreciation_method: Optional[str] = Field(None, pattern="^(straight|double_declining|sum_of_years)$")
    dept_id: Optional[UUID] = None
    status: Optional[str] = Field(None, pattern="^(in_use|disposed|cleared)$")


class FixedAssetResponse(BaseModel):
    """Fixed asset card response."""
    id: UUID
    code: str
    name: str
    category: str
    purchase_date: date
    purchase_amount: Decimal
    salvage_value: Decimal
    useful_life_months: int
    depreciation_method: str
    monthly_depreciation: Decimal
    accumulated_depreciation: Decimal
    net_value: Decimal
    status: str
    dept_id: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DepreciateRequest(BaseModel):
    """POST /fixed-assets/{id}/depreciate request."""
    period_id: UUID


class DepreciateBatchRequest(BaseModel):
    """POST /fixed-assets/depreciate-batch request."""
    period_id: UUID


class DepreciateResponse(BaseModel):
    """Depreciation result."""
    asset_id: UUID
    asset_name: str
    monthly_depreciation: Decimal
    accumulated_depreciation: Decimal
    net_value: Decimal


class DisposeRequest(BaseModel):
    """POST /fixed-assets/{id}/dispose request."""
    period_id: UUID
    disposal_date: date
    disposal_amount: Decimal = Decimal("0")


class AssetReportResponse(BaseModel):
    """GET /fixed-assets/reports response."""
    period: dict
    total_assets: int
    total_original_value: Decimal
    total_accumulated_depreciation: Decimal
    total_net_value: Decimal
    by_category: List[dict]  # {category, count, original, depreciation, net}
    by_status: List[dict]    # {status, count, net_value}
