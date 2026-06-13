"""Cashier routes (§3.10).

Cash Journal:
  GET  /cash-journals          — list cash journal entries
  POST /cash-journals          — record cash journal entry

Bank Journal:
  GET  /bank-journals          — list bank journal entries
  POST /bank-journals/import   — import bank statements (Excel)

Bank Reconciliation:
  POST /bank-reconcile         — reconcile bank statement with ledger
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.schemas.common import PaginatedResponse

router = APIRouter()
bank_router = APIRouter()
reconcile_router = APIRouter()


# ── Cash Journal ──────────────────────────────────────────────


@router.get("")
async def list_cash_journals(
    account_id: UUID = Query(...),
    date_from: str = Query(None),
    date_to: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("cashier:use")),
) -> PaginatedResponse[dict]:
    """List cash journal entries for an account."""
    raise NotImplementedError(
        "list_cash_journals:\n"
        "1. Query CashJournal WHERE account_id=... AND date BETWEEN ...\n"
        "2. ORDER BY date, created_at\n"
        "3. Paginate"
    )


@router.post("", status_code=201)
async def create_cash_journal(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("cashier:use")),
) -> dict:
    """Record a cash journal entry.

    Body: {date, period_id, voucher_id, account_id, summary, debit, credit, serial_no, counterparty}
    """
    raise NotImplementedError(
        "create_cash_journal:\n"
        "1. Validate account is a cash account (accounts.is_cash=TRUE)\n"
        "2. Calculate running balance from previous entries for this account\n"
        "3. Create CashJournal entry\n"
        "4. Return created entry"
    )


# ── Bank Journal ──────────────────────────────────────────────


@bank_router.get("")
async def list_bank_journals(
    account_id: UUID = Query(...),
    date_from: str = Query(None),
    date_to: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("cashier:use")),
) -> PaginatedResponse[dict]:
    """List bank journal entries."""
    raise NotImplementedError(
        "list_bank_journals:\n"
        "1. Query BankJournal WHERE account_id=... AND date BETWEEN ...\n"
        "2. ORDER BY date, created_at\n"
        "3. Paginate"
    )


@bank_router.post("/import")
async def import_bank_journals(
    file: UploadFile,
    account_id: UUID = Query(...),
    period_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("cashier:use")),
) -> dict:
    """Import bank statement from Excel file.

    Expected columns: date, summary, debit, credit, balance, serial_no, counterparty.
    """
    raise NotImplementedError(
        "import_bank_journals:\n"
        "1. Parse Excel file (openpyxl)\n"
        "2. Validate header columns\n"
        "3. For each row: create BankJournal entry\n"
        "4. Deduplicate by (date, amount, serial_no)\n"
        "5. Return {imported: N, skipped: M, errors: [...]}"
    )


# ── Bank Reconciliation ───────────────────────────────────────


@reconcile_router.post("")
async def bank_reconcile(
    account_id: UUID = Query(...),
    period_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("cashier:use")),
) -> dict:
    """Reconcile bank journal with accounting ledger.

    Compares bank journal entries with posted voucher entries for the account.
    Returns matched, unmatched in bank, unmatched in ledger.
    """
    raise NotImplementedError(
        "bank_reconcile:\n"
        "1. Get all posted voucher_entries for this account in the period\n"
        "2. Get all bank_journal entries for this account in the period\n"
        "3. Match by date+amount within tolerance\n"
        "4. Return {\n"
        "     matched: [{ledger_entry, bank_entry}],\n"
        "     unmatched_ledger: [...],  # entries in ledger but not in bank statement\n"
        "     unmatched_bank: [...],    # entries in bank statement but not in ledger\n"
        "     ledger_balance, bank_balance, difference\n"
        "   }"
    )
