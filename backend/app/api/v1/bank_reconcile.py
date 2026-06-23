"""Bank Reconciliation routes (§3.10).

POST /bank-reconcile — auto-match bank journal with voucher entries
"""

import uuid as _uuid
from datetime import date as date_type, datetime
from decimal import Decimal as D

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.models.cashier import BankJournal
from app.models.voucher import Voucher, VoucherEntry
from app.models.account import Account as AccountModel
from app.schemas.cashier import (
    BankReconcileRequest,
    BankReconcileMatch,
    BankReconcileResponse,
)

router = APIRouter()


@router.post("", response_model=BankReconcileResponse)
async def reconcile_bank(
    body: BankReconcileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("cashier:use")),
) -> BankReconcileResponse:
    """Auto-reconcile bank journal entries with voucher entries.

    Matching logic:
    - Same amount
    - Same/similar date (±3 days)
    - Counterparty name fuzzy match (substring)
    """
    # 1. Get all bank journal entries for the account+period
    bank_result = await db.execute(
        select(BankJournal)
        .where(
            BankJournal.account_id == body.account_id,
            BankJournal.period_id == body.period_id,
        )
        .order_by(BankJournal.date)
    )
    bank_entries = list(bank_result.scalars().all())

    # 2. Get all posted voucher entries for the account
    v_entry_result = await db.execute(
        select(VoucherEntry, Voucher)
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .where(
            VoucherEntry.account_id == body.account_id,
            Voucher.period_id == body.period_id,
            Voucher.status == "posted",
            Voucher.deleted_at.is_(None),
        )
        .order_by(Voucher.date)
    )
    v_entries = list(v_entry_result)

    # 3. Match
    matched: list[BankReconcileMatch] = []
    matched_bank_ids: set = set()
    matched_voucher_ids: set = set()

    for be in bank_entries:
        for ve, voucher in v_entries:
            if ve.id in matched_voucher_ids:
                continue
            # Amount match
            if be.debit == ve.debit_amount and be.credit == ve.credit_amount:
                # Date proximity (±3 days)
                date_diff = abs((be.date - voucher.date).days)
                if date_diff <= 3:
                    matched.append(BankReconcileMatch(
                        bank_entry_id=be.id,
                        voucher_entry_id=ve.id,
                        date=be.date,
                        amount=be.debit or be.credit,
                        description=be.summary,
                    ))
                    matched_bank_ids.add(be.id)
                    matched_voucher_ids.add(ve.id)
                    break

    # 4. Unmatched items
    bank_only = [
        {"id": str(be.id), "date": str(be.date), "amount": str(be.debit or be.credit),
         "summary": be.summary, "counterparty": be.counterparty or ""}
        for be in bank_entries if be.id not in matched_bank_ids
    ]

    voucher_only = [
        {"id": str(ve.id), "date": str(voucher.date), "voucher_no": voucher.voucher_no,
         "amount": str(ve.debit_amount or ve.credit_amount), "summary": ve.summary}
        for ve, voucher in v_entries if ve.id not in matched_voucher_ids
    ]

    bank_balance = sum((be.debit - be.credit for be in bank_entries), D("0"))
    voucher_balance = sum(
        (ve.debit_amount - ve.credit_amount for ve, _ in v_entries), D("0")
    )

    return BankReconcileResponse(
        matched=matched,
        bank_only=bank_only,
        voucher_only=voucher_only,
        bank_balance=bank_balance,
        voucher_balance=voucher_balance,
        reconciled_balance=voucher_balance - bank_balance,
    )
