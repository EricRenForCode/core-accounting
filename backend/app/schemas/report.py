"""Report and statement schemas (§3.6, §3.7)."""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID


# ── Trial Balance ─────────────────────────────────────────────


class TrialBalanceRow(BaseModel):
    """Single row in trial balance report."""

    account_id: UUID
    code: str
    name: str
    level: int
    opening_debit: Decimal = Decimal("0")
    opening_credit: Decimal = Decimal("0")
    current_debit: Decimal = Decimal("0")
    current_credit: Decimal = Decimal("0")
    closing_debit: Decimal = Decimal("0")
    closing_credit: Decimal = Decimal("0")
    opening_balance: Decimal = Decimal("0")
    closing_balance: Decimal = Decimal("0")
    children: List["TrialBalanceRow"] = Field(default_factory=list)


class TrialBalanceSummary(BaseModel):
    """Summary row for trial balance."""

    total_opening_debit: Decimal
    total_opening_credit: Decimal
    total_current_debit: Decimal
    total_current_credit: Decimal
    total_closing_debit: Decimal
    total_closing_credit: Decimal


class TrialBalanceResponse(BaseModel):
    """GET /reports/trial-balance response (§3.6)."""

    period: dict  # {year, month}
    rows: List[TrialBalanceRow]
    summary: TrialBalanceSummary


# ── General Ledger ────────────────────────────────────────────


class GeneralLedgerRow(BaseModel):
    """Row in general ledger."""

    date: date
    voucher_no: str
    summary: str
    debit: Decimal
    credit: Decimal
    balance_direction: str  # Debit/Credit
    balance: Decimal


class GeneralLedgerResponse(BaseModel):
    """GET /reports/general-ledger response."""

    period: dict
    account: dict
    opening_balance: Decimal
    rows: List[GeneralLedgerRow]
    closing_balance: Decimal


# ── Detail Ledger (三栏明细账) ─────────────────────────────────


class DetailLedgerRow(BaseModel):
    """Row in detail ledger."""

    date: date
    voucher_no: str
    summary: str
    debit: Decimal
    credit: Decimal
    balance_direction: str
    balance: Decimal


class DetailLedgerResponse(BaseModel):
    """GET /reports/detail-ledger/{account_id} response."""

    period: dict
    account: dict
    opening_balance: Decimal
    opening_direction: str
    rows: List[DetailLedgerRow]
    current_debit: Decimal
    current_credit: Decimal
    closing_balance: Decimal
    closing_direction: str


# ── Journal / Multi-Column / Quantity ─────────────────────────


class JournalRow(BaseModel):
    """Row in chronological journal (序时账)."""

    date: date
    voucher_no: str
    account_code: str
    account_name: str
    summary: str
    debit: Decimal
    credit: Decimal


class JournalResponse(BaseModel):
    """GET /reports/journal response."""

    period: dict
    rows: List[JournalRow]
    total_debit: Decimal
    total_credit: Decimal


class QuantityLedgerRow(BaseModel):
    """Row in quantity-amount ledger (数量金额账)."""

    date: date
    voucher_no: str
    summary: str
    quantity_in: Decimal
    amount_in: Decimal
    quantity_out: Decimal
    amount_out: Decimal
    quantity_balance: Decimal
    amount_balance: Decimal


class QuantityLedgerResponse(BaseModel):
    """GET /reports/quantity-ledger/{account_id} response."""

    period: dict
    account: dict
    unit: str
    opening_quantity: Decimal
    opening_amount: Decimal
    rows: List[QuantityLedgerRow]
    closing_quantity: Decimal
    closing_amount: Decimal


# ── Multi-Column Ledger (§3.6) ─────────────────────────────────


class MultiColumnLedgerColumn(BaseModel):
    """Dynamic column in multi-column ledger (对方科目)."""

    account_code: str
    account_name: str


class MultiColumnLedgerRow(BaseModel):
    """Row in multi-column ledger."""

    date: date
    voucher_no: str
    summary: str
    column_values: dict  # {account_code: {"debit": ..., "credit": ...}}
    total_debit: Decimal
    total_credit: Decimal


class MultiColumnLedgerResponse(BaseModel):
    """GET /reports/multi-column-ledger/{account_id} response."""

    period: dict
    account: dict
    columns: List[MultiColumnLedgerColumn]
    rows: List[MultiColumnLedgerRow]
    total_debit: Decimal
    total_credit: Decimal


# ── Financial Statements (§3.7) ───────────────────────────────


class StatementItem(BaseModel):
    """Single line item in a financial statement."""

    name: str
    code: Optional[str] = None
    closing: Decimal = Decimal("0")
    opening: Decimal = Decimal("0")


class StatementSection(BaseModel):
    """Section in a financial statement."""

    label: str
    items: List[StatementItem]
    subtotal: dict  # {closing, opening}


class BalanceSheetResponse(BaseModel):
    """GET /statements/balance-sheet response."""

    period: dict
    template: dict  # {name, id}
    sections: List[StatementSection]
    totals: dict


class IncomeStatementResponse(BaseModel):
    """GET /statements/income response."""

    period: dict
    template: dict
    sections: List[StatementSection]
    totals: dict


class CashFlowStatementResponse(BaseModel):
    """GET /statements/cash-flow response."""

    period: dict
    template: dict
    sections: List[StatementSection]
    totals: dict


class StatementExportRequest(BaseModel):
    """POST /statements/export request body."""

    type: str = Field(..., pattern="^(balance_sheet|income|cash_flow|trial_balance)$")
    period_id: UUID
    format: str = Field(default="excel", pattern="^(excel|pdf)$")
