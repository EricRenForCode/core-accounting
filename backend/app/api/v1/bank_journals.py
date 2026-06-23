"""Bank Journal routes (§3.10).

GET  /bank-journals           — list bank journal entries
POST /bank-journals           — create a journal entry
POST /bank-journals/import    — import bank statement (Excel)
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
from app.models.voucher import Voucher
from app.models.account import Account as AccountModel
from app.schemas.cashier import (
    BankJournalCreate,
    BankJournalImportRequest,
    BankJournalImportResponse,
    BankJournalResponse,
    BankJournalRow,
)

router = APIRouter()


@router.get("", response_model=BankJournalResponse)
async def list_bank_journals(
    account_id: _uuid.UUID = Query(...),
    date_from: str = Query(None),
    date_to: str = Query(None),
    period_id: _uuid.UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("cashier:use")),
) -> BankJournalResponse:
    """List bank journal entries for an account."""
    acct_result = await db.execute(
        select(AccountModel).where(AccountModel.id == account_id)
    )
    account = acct_result.scalar_one_or_none()
    if not account:
        raise HTTPException(404, "科目不存在")

    q = select(BankJournal, Voucher).join(
        Voucher, BankJournal.voucher_id == Voucher.id, isouter=True
    ).where(BankJournal.account_id == account_id)

    if period_id:
        q = q.where(BankJournal.period_id == period_id)

    if date_from:
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d").date()
            q = q.where(BankJournal.date >= start)
        except ValueError:
            raise HTTPException(400, f"日期格式错误: {date_from}")

    if date_to:
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d").date()
            q = q.where(BankJournal.date <= end)
        except ValueError:
            raise HTTPException(400, f"日期格式错误: {date_to}")

    q = q.order_by(BankJournal.date, BankJournal.created_at)

    result = await db.execute(q)
    rows: list[BankJournalRow] = []
    total_debit = D("0")
    total_credit = D("0")
    balance = D("0")

    for bj, voucher in result:
        balance = balance + bj.debit - bj.credit
        total_debit += bj.debit
        total_credit += bj.credit

        rows.append(BankJournalRow(
            id=bj.id,
            date=bj.date,
            voucher_id=bj.voucher_id,
            voucher_no=voucher.voucher_no if voucher else None,
            account_id=bj.account_id,
            account_code=account.code,
            account_name=account.name,
            summary=bj.summary,
            debit=bj.debit,
            credit=bj.credit,
            balance=balance,
            serial_no=bj.serial_no,
            counterparty=bj.counterparty,
            created_at=bj.created_at,
        ))

    return BankJournalResponse(
        account={"id": str(account.id), "code": account.code, "name": account.name},
        period={},
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
        closing_balance=balance,
    )


@router.post("/import", response_model=BankJournalImportResponse)
async def import_bank_journals(
    body: BankJournalImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("cashier:use")),
) -> BankJournalImportResponse:
    """Import bank statement rows."""
    from app.models.period import Period

    # Validate account
    acct_result = await db.execute(
        select(AccountModel).where(AccountModel.id == body.account_id)
    )
    account = acct_result.scalar_one_or_none()
    if not account:
        raise HTTPException(404, "科目不存在")

    # Validate period
    period_result = await db.execute(
        select(Period).where(Period.id == body.period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(404, "会计期间不存在")

    # Get last balance
    last_result = await db.execute(
        select(BankJournal)
        .where(BankJournal.account_id == body.account_id)
        .order_by(BankJournal.date.desc(), BankJournal.created_at.desc())
        .limit(1)
    )
    last = last_result.scalar_one_or_none()
    balance = last.balance if last else D("0")

    imported = 0
    errors: list[dict] = []

    for i, row in enumerate(body.rows):
        try:
            balance = balance + row.debit - row.credit
            bj = BankJournal(
                date=row.date,
                period_id=body.period_id,
                voucher_id=_uuid.uuid4(),
                account_id=body.account_id,
                summary=row.summary,
                debit=row.debit,
                credit=row.credit,
                balance=balance,
                serial_no=row.serial_no,
                counterparty=row.counterparty,
            )
            db.add(bj)
            imported += 1
        except Exception as e:
            errors.append({"row": i + 1, "error": str(e)})

    await db.commit()

    return BankJournalImportResponse(imported=imported, errors=errors)
