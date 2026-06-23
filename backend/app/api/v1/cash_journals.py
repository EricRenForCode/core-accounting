"""Cash Journal routes (§3.10).

GET  /cash-journals           — list cash journal entries
POST /cash-journals           — create a journal entry
"""

import uuid as _uuid
from datetime import date as date_type, datetime
from decimal import Decimal as D

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.models.cashier import CashJournal
from app.models.voucher import Voucher
from app.models.account import Account as AccountModel
from app.schemas.cashier import (
    CashJournalCreate,
    CashJournalResponse,
    CashJournalRow,
)

router = APIRouter()


@router.get("", response_model=CashJournalResponse)
async def list_cash_journals(
    account_id: _uuid.UUID = Query(...),
    date_from: str = Query(None),
    date_to: str = Query(None),
    period_id: _uuid.UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("cashier:use")),
) -> CashJournalResponse:
    """List cash journal entries for an account."""
    # Get account
    acct_result = await db.execute(
        select(AccountModel).where(AccountModel.id == account_id)
    )
    account = acct_result.scalar_one_or_none()
    if not account:
        raise HTTPException(404, "科目不存在")

    # Build query
    q = select(CashJournal, Voucher).join(
        Voucher, CashJournal.voucher_id == Voucher.id, isouter=True
    ).where(CashJournal.account_id == account_id)

    if period_id:
        q = q.where(CashJournal.period_id == period_id)

    if date_from:
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d").date()
            q = q.where(CashJournal.date >= start)
        except ValueError:
            raise HTTPException(400, f"日期格式错误: {date_from}")

    if date_to:
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d").date()
            q = q.where(CashJournal.date <= end)
        except ValueError:
            raise HTTPException(400, f"日期格式错误: {date_to}")

    q = q.order_by(CashJournal.date, CashJournal.created_at)

    result = await db.execute(q)
    rows: list[CashJournalRow] = []
    total_debit = D("0")
    total_credit = D("0")
    balance = D("0")

    for cj, voucher in result:
        balance = balance + cj.debit - cj.credit
        total_debit += cj.debit
        total_credit += cj.credit

        rows.append(CashJournalRow(
            id=cj.id,
            date=cj.date,
            voucher_id=cj.voucher_id,
            voucher_no=voucher.voucher_no if voucher else None,
            account_id=cj.account_id,
            account_code=account.code,
            account_name=account.name,
            summary=cj.summary,
            debit=cj.debit,
            credit=cj.credit,
            balance=balance,
            serial_no=cj.serial_no,
            counterparty=cj.counterparty,
            created_at=cj.created_at,
        ))

    return CashJournalResponse(
        account={"id": str(account.id), "code": account.code, "name": account.name},
        period={},
        opening_balance=D("0"),
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
        closing_balance=balance,
    )


@router.post("", response_model=CashJournalRow, status_code=201)
async def create_cash_journal(
    body: CashJournalCreate,
    period_id: _uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("cashier:use")),
) -> CashJournalRow:
    """Create a manual cash journal entry."""
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
        select(Period).where(Period.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(404, "会计期间不存在")

    # Get running balance
    last_result = await db.execute(
        select(CashJournal)
        .where(CashJournal.account_id == body.account_id)
        .order_by(CashJournal.date.desc(), CashJournal.created_at.desc())
        .limit(1)
    )
    last = last_result.scalar_one_or_none()
    prev_balance = last.balance if last else D("0")
    new_balance = prev_balance + body.debit - body.credit

    # Create a synthetic voucher_id for standalone journal entries
    # In production this would be linked to a real voucher
    cj = CashJournal(
        date=body.date,
        period_id=period_id,
        voucher_id=_uuid.uuid4(),  # placeholder — would be linked to real voucher
        account_id=body.account_id,
        summary=body.summary,
        debit=body.debit,
        credit=body.credit,
        balance=new_balance,
        counterparty=body.counterparty,
    )
    db.add(cj)
    await db.commit()
    await db.refresh(cj)

    return CashJournalRow(
        id=cj.id,
        date=cj.date,
        voucher_id=cj.voucher_id,
        account_id=cj.account_id,
        account_code=account.code,
        account_name=account.name,
        summary=cj.summary,
        debit=cj.debit,
        credit=cj.credit,
        balance=cj.balance,
        serial_no=cj.serial_no,
        counterparty=cj.counterparty,
        created_at=cj.created_at,
    )
