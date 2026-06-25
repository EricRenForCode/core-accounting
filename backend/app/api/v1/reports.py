"""Reports and financial statements routes (§3.6, §3.7).

Reports (§3.6):
  GET /reports/trial-balance              — 科目余额表
  GET /reports/general-ledger             — 总账
  GET /reports/detail-ledger/{account_id} — 三栏明细账
  GET /reports/multi-column-ledger/{account_id} — 多栏明细账
  GET /reports/journal                    — 序时账
  GET /reports/quantity-ledger/{account_id}   — 数量金额账

Statements (§3.7):
  GET  /statements/balance-sheet — 资产负债表
  GET  /statements/income        — 利润表
  GET  /statements/cash-flow     — 现金流量表
  GET  /statements/templates     — 报表模板列表
  POST /statements/export        — 导出报表
"""

from uuid import UUID

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.models.voucher import Voucher, VoucherEntry
from app.schemas.report import (
    BalanceSheetResponse,
    CashFlowStatementResponse,
    DetailLedgerResponse,
    GeneralLedgerResponse,
    IncomeStatementResponse,
    JournalResponse,
    MultiColumnLedgerColumn,
    MultiColumnLedgerResponse,
    MultiColumnLedgerRow,
    QuantityLedgerResponse,
    StatementExportRequest,
    StatementItem,
    StatementSection,
    TrialBalanceResponse,
)

report_router = APIRouter()
statement_router = APIRouter()


# ── Reports (§3.6) ────────────────────────────────────────────


@report_router.get("/trial-balance", response_model=TrialBalanceResponse)
async def trial_balance(
    period_id: UUID = Query(...),
    level: int = Query(None, ge=1, le=4),
    include_zero: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:read")),
) -> TrialBalanceResponse:
    """科目余额表 — trial balance with tree structure (§7.2)."""
    from app.models.period import AccountBalance, Period
    from app.models.account import Account as AccountModel
    from app.schemas.report import TrialBalanceRow, TrialBalanceSummary

    # 1. Get period info
    period_result = await db.execute(
        select(Period).where(Period.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    # 2. Get all enabled accounts
    acct_result = await db.execute(
        select(AccountModel)
        .where(AccountModel.is_enabled == True)
        .order_by(AccountModel.code)
    )
    accounts: list[AccountModel] = list(acct_result.scalars().all())

    # 3. Get all balances for this period
    bal_result = await db.execute(
        select(AccountBalance).where(AccountBalance.period_id == period_id)
    )
    balances: dict[UUID, AccountBalance] = {
        b.account_id: b for b in bal_result.scalars().all()
    }

    # 4. Build account tree
    accounts_by_id = {a.id: a for a in accounts}
    children_by_parent: dict[UUID, list[AccountModel]] = {}
    roots: list[AccountModel] = []

    for acct in accounts:
        if level is not None and acct.level > level:
            continue
        if acct.parent_id:
            children_by_parent.setdefault(acct.parent_id, []).append(acct)
        else:
            roots.append(acct)

    # 5. Build rows recursively
    def _build_row(acct: AccountModel) -> TrialBalanceRow:
        bal = balances.get(acct.id)
        opening_debit = bal.opening_debit if bal else Decimal("0")
        opening_credit = bal.opening_credit if bal else Decimal("0")
        current_debit = bal.current_debit if bal else Decimal("0")
        current_credit = bal.current_credit if bal else Decimal("0")
        closing_debit = bal.closing_debit if bal else Decimal("0")
        closing_credit = bal.closing_credit if bal else Decimal("0")

        # Direction-aware display balance
        if acct.dc_type == "D":
            opening_balance = opening_debit - opening_credit
            closing_balance = closing_debit - closing_credit
        else:
            opening_balance = opening_credit - opening_debit
            closing_balance = closing_credit - closing_debit

        # Aggregate children
        child_rows: list[TrialBalanceRow] = []
        for child in children_by_parent.get(acct.id, []):
            child_row = _build_row(child)
            # Add child amounts to parent
            opening_debit += child_row.opening_debit
            opening_credit += child_row.opening_credit
            current_debit += child_row.current_debit
            current_credit += child_row.current_credit
            closing_debit += child_row.closing_debit
            closing_credit += child_row.closing_credit

            # Skip zero-balance children if not include_zero
            if include_zero or _has_balance(child_row):
                child_rows.append(child_row)

        # Recalculate parent's display balance after aggregation
        if acct.dc_type == "D":
            opening_balance = opening_debit - opening_credit
            closing_balance = closing_debit - closing_credit
        else:
            opening_balance = opening_credit - opening_debit
            closing_balance = closing_credit - closing_debit

        return TrialBalanceRow(
            account_id=acct.id,
            code=acct.code,
            name=acct.name,
            level=acct.level,
            opening_debit=opening_debit,
            opening_credit=opening_credit,
            current_debit=current_debit,
            current_credit=current_credit,
            closing_debit=closing_debit,
            closing_credit=closing_credit,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            children=child_rows,
        )

    rows = [_build_row(r) for r in roots]

    # Filter out zero-balance roots
    if not include_zero:
        rows = [r for r in rows if _has_balance(r)]

    # 6. Compute summary
    def _sum(fn):
        return sum((fn(r) for r in rows), Decimal("0"))

    summary = TrialBalanceSummary(
        total_opening_debit=_sum(lambda r: r.opening_debit),
        total_opening_credit=_sum(lambda r: r.opening_credit),
        total_current_debit=_sum(lambda r: r.current_debit),
        total_current_credit=_sum(lambda r: r.current_credit),
        total_closing_debit=_sum(lambda r: r.closing_debit),
        total_closing_credit=_sum(lambda r: r.closing_credit),
    )

    return TrialBalanceResponse(
        period={"year": period.year, "month": period.month},
        rows=rows,
        summary=summary,
    )


def _has_balance(row) -> bool:
    """Check if a TrialBalanceRow (or any descendant) has non-zero balances."""
    if any(
        v != Decimal("0")
        for v in [
            row.opening_debit, row.opening_credit,
            row.current_debit, row.current_credit,
            row.closing_debit, row.closing_credit,
        ]
    ):
        return True
    return any(_has_balance(c) for c in row.children)


@report_router.get("/general-ledger", response_model=GeneralLedgerResponse)
async def general_ledger(
    period_id: UUID = Query(...),
    account_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ledger:read")),
) -> GeneralLedgerResponse:
    """总账 — general ledger for a single account in a period."""
    from app.models.period import AccountBalance, Period
    from app.models.account import Account as AccountModel
    from app.schemas.report import GeneralLedgerRow

    # 1. Get account
    acct_result = await db.execute(
        select(AccountModel).where(AccountModel.id == account_id)
    )
    account = acct_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="科目不存在")

    # 2. Get period
    period_result = await db.execute(
        select(Period).where(Period.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    # 3. Get opening balance
    bal_result = await db.execute(
        select(AccountBalance).where(
            AccountBalance.period_id == period_id,
            AccountBalance.account_id == account_id,
        )
    )
    bal = bal_result.scalar_one_or_none()

    if account.dc_type == "D":
        opening_balance = (
            (bal.opening_debit - bal.opening_credit) if bal else Decimal("0")
        )
    else:
        opening_balance = (
            (bal.opening_credit - bal.opening_debit) if bal else Decimal("0")
        )

    # 4. Query posted entries for this account in the period
    entry_result = await db.execute(
        select(VoucherEntry, Voucher)
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .where(
            VoucherEntry.account_id == account_id,
            Voucher.period_id == period_id,
            Voucher.status == "posted",
            Voucher.deleted_at.is_(None),
        )
        .order_by(Voucher.date, Voucher.voucher_no, VoucherEntry.row_number)
    )

    rows: list[GeneralLedgerRow] = []
    running = opening_balance

    for entry, voucher in entry_result:
        diff = entry.debit_amount - entry.credit_amount
        if account.dc_type == "D":
            running += diff
            direction = "借" if running >= 0 else "贷"
        else:
            running = running + entry.credit_amount - entry.debit_amount
            direction = "贷" if running >= 0 else "借"

        rows.append(GeneralLedgerRow(
            date=voucher.date,
            voucher_no=voucher.voucher_no,
            summary=entry.summary,
            debit=entry.debit_amount,
            credit=entry.credit_amount,
            balance_direction=direction,
            balance=abs(running),
        ))

    return GeneralLedgerResponse(
        period={"year": period.year, "month": period.month},
        account={"id": str(account.id), "code": account.code, "name": account.name},
        opening_balance=opening_balance,
        rows=rows,
        closing_balance=abs(running) if rows else opening_balance,
    )


@report_router.get("/detail-ledger/{account_id}", response_model=DetailLedgerResponse)
async def detail_ledger(
    account_id: UUID,
    period_id: UUID = Query(...),
    date_from: str = Query(None),
    date_to: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ledger:read")),
) -> DetailLedgerResponse:
    """三栏明细账 — three-column detail ledger with debit/credit/balance."""
    from datetime import datetime
    from app.models.period import AccountBalance, Period
    from app.models.account import Account as AccountModel
    from app.schemas.report import DetailLedgerRow

    # 1. Get account
    acct_result = await db.execute(
        select(AccountModel).where(AccountModel.id == account_id)
    )
    account = acct_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="科目不存在")

    # 2. Get period
    period_result = await db.execute(
        select(Period).where(Period.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    # 3. Get opening balance
    bal_result = await db.execute(
        select(AccountBalance).where(
            AccountBalance.period_id == period_id,
            AccountBalance.account_id == account_id,
        )
    )
    bal = bal_result.scalar_one_or_none()

    if account.dc_type == "D":
        opening_balance = (
            (bal.opening_debit - bal.opening_credit) if bal else Decimal("0")
        )
        opening_direction = "借" if opening_balance >= 0 else "贷"
    else:
        opening_balance = (
            (bal.opening_credit - bal.opening_debit) if bal else Decimal("0")
        )
        opening_direction = "贷" if opening_balance >= 0 else "借"

    # 4. Query posted entries
    query = (
        select(VoucherEntry, Voucher)
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .where(
            VoucherEntry.account_id == account_id,
            Voucher.period_id == period_id,
            Voucher.status == "posted",
            Voucher.deleted_at.is_(None),
        )
    )

    if date_from:
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d").date()
            query = query.where(Voucher.date >= start)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"日期格式错误: {date_from}")
    if date_to:
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d").date()
            query = query.where(Voucher.date <= end)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"日期格式错误: {date_to}")

    query = query.order_by(Voucher.date, Voucher.voucher_no, VoucherEntry.row_number)

    result = await db.execute(query)

    rows: list[DetailLedgerRow] = []
    running = opening_balance
    current_debit = Decimal("0")
    current_credit = Decimal("0")

    for entry, voucher in result:
        current_debit += entry.debit_amount
        current_credit += entry.credit_amount

        if account.dc_type == "D":
            running = running + entry.debit_amount - entry.credit_amount
            direction = "借" if running >= 0 else "贷"
        else:
            running = running + entry.credit_amount - entry.debit_amount
            direction = "贷" if running >= 0 else "借"

        rows.append(DetailLedgerRow(
            date=voucher.date,
            voucher_no=voucher.voucher_no,
            summary=entry.summary,
            debit=entry.debit_amount,
            credit=entry.credit_amount,
            balance_direction=direction,
            balance=abs(running),
        ))

    if account.dc_type == "D":
        closing_balance = running
        closing_direction = "借" if closing_balance >= 0 else "贷"
    else:
        closing_balance = running
        closing_direction = "贷" if closing_balance >= 0 else "借"

    return DetailLedgerResponse(
        period={"year": period.year, "month": period.month},
        account={"id": str(account.id), "code": account.code, "name": account.name},
        opening_balance=abs(opening_balance),
        opening_direction=opening_direction,
        rows=rows,
        current_debit=current_debit,
        current_credit=current_credit,
        closing_balance=abs(closing_balance),
        closing_direction=closing_direction,
    )


@report_router.get(
    "/multi-column-ledger/{account_id}",
    response_model=MultiColumnLedgerResponse,
)
async def multi_column_ledger(
    account_id: UUID,
    period_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ledger:read")),
) -> MultiColumnLedgerResponse:
    """多栏明细账 — multi-column detail ledger by counterparty accounts.

    For a given account, find all posted vouchers where it appears.
    For each voucher, show the amounts broken down by the other accounts
    (对方科目/counterparty accounts) in the same voucher as dynamic columns.

    Columns are sorted by account code; each column has its own debit/credit
    sub-columns showing the amount for that counterparty account in each row.
    """
    from collections import defaultdict
    from app.models.period import Period
    from app.models.account import Account as AccountModel

    # 1. Get account
    acct_result = await db.execute(
        select(AccountModel).where(AccountModel.id == account_id)
    )
    account = acct_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="科目不存在")

    # 2. Get period
    period_result = await db.execute(
        select(Period).where(Period.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    # 3. Find all vouchers where this account appears (posted only)
    voucher_subq = (
        select(Voucher.id)
        .join(VoucherEntry, VoucherEntry.voucher_id == Voucher.id)
        .where(
            VoucherEntry.account_id == account_id,
            Voucher.period_id == period_id,
            Voucher.status == "posted",
            Voucher.deleted_at.is_(None),
        )
        .distinct()
        .subquery()
    )

    # 4. Get ALL entries for these vouchers (including the target account)
    all_entries_result = await db.execute(
        select(VoucherEntry, Voucher, AccountModel)
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .join(AccountModel, VoucherEntry.account_id == AccountModel.id)
        .where(Voucher.id.in_(select(voucher_subq.c.id)))
        .order_by(Voucher.date, Voucher.voucher_no, VoucherEntry.row_number)
    )

    # 5. Build data structures
    # voucher_id -> {summary, date, voucher_no, entries: {account_code: {debit, credit}}}
    voucher_data: dict = {}
    counterparty_codes: set[str] = set()
    account_code_map: dict[str, str] = {}  # code -> name

    for entry, voucher, entry_account in all_entries_result:
        vid = voucher.id
        if vid not in voucher_data:
            voucher_data[vid] = {
                "date": voucher.date,
                "voucher_no": voucher.voucher_no,
                "entries": {},
                "summary": "",
            }
            # Use the target account's entry summary for the row

        code = entry_account.code
        name = entry_account.name
        account_code_map[code] = name

        if code not in voucher_data[vid]["entries"]:
            voucher_data[vid]["entries"][code] = {
                "debit": Decimal("0"),
                "credit": Decimal("0"),
            }
        voucher_data[vid]["entries"][code]["debit"] += entry.debit_amount
        voucher_data[vid]["entries"][code]["credit"] += entry.credit_amount

        # Track the target account's summary
        if str(entry.account_id) == str(account_id):
            voucher_data[vid]["summary"] = entry.summary

        # Track counterparty columns (exclude the target account itself)
        if code != account.code:
            counterparty_codes.add(code)

    # 6. Sort counterparty columns by code
    sorted_columns = sorted(counterparty_codes)

    # 7. Build rows
    rows: list[MultiColumnLedgerRow] = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for vid in sorted(voucher_data.keys(), key=lambda v: (
        voucher_data[v]["date"], voucher_data[v]["voucher_no"]
    )):
        vd = voucher_data[vid]
        entries = vd["entries"]

        # Amounts for the target account (this row's totals)
        target = entries.get(account.code, {"debit": Decimal("0"), "credit": Decimal("0")})
        row_debit = target["debit"]
        row_credit = target["credit"]
        total_debit += row_debit
        total_credit += row_credit

        # Build column values — only for counterparty accounts
        column_values: dict[str, dict] = {}
        for col_code in sorted_columns:
            if col_code in entries:
                col = entries[col_code]
                column_values[col_code] = {
                    "debit": str(col["debit"]),
                    "credit": str(col["credit"]),
                }
            else:
                column_values[col_code] = {"debit": "0", "credit": "0"}

        rows.append(MultiColumnLedgerRow(
            date=vd["date"],
            voucher_no=vd["voucher_no"],
            summary=vd["summary"],
            column_values=column_values,
            total_debit=row_debit,
            total_credit=row_credit,
        ))

    # 8. Build columns
    columns = [
        MultiColumnLedgerColumn(
            account_code=code, account_name=account_code_map[code]
        )
        for code in sorted_columns
    ]

    return MultiColumnLedgerResponse(
        period={"year": period.year, "month": period.month},
        account={"id": str(account.id), "code": account.code, "name": account.name},
        columns=columns,
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
    )


@report_router.get("/journal", response_model=JournalResponse)
async def journal(
    period_id: UUID = Query(...),
    date_from: str = Query(None),
    date_to: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ledger:read")),
) -> JournalResponse:
    """序时账 — chronological journal listing all posted entries."""
    from datetime import date as dt_date, datetime
    from app.models.period import Period
    from app.models.account import Account as AccountModel
    from app.schemas.report import JournalRow
    from sqlalchemy.orm import selectinload

    # 1. Get period
    period_result = await db.execute(
        select(Period).where(Period.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    # 2. Query posted entries
    query = (
        select(VoucherEntry, Voucher, AccountModel)
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .join(AccountModel, VoucherEntry.account_id == AccountModel.id)
        .where(
            Voucher.period_id == period_id,
            Voucher.status == "posted",
            Voucher.deleted_at.is_(None),
        )
    )

    if date_from:
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d").date()
            query = query.where(Voucher.date >= start)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"日期格式错误: {date_from}")
    if date_to:
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d").date()
            query = query.where(Voucher.date <= end)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"日期格式错误: {date_to}")

    query = query.order_by(Voucher.date, Voucher.voucher_no, VoucherEntry.row_number)

    result = await db.execute(query)

    rows: list[JournalRow] = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for entry, voucher, account in result:
        total_debit += entry.debit_amount
        total_credit += entry.credit_amount
        rows.append(JournalRow(
            date=voucher.date,
            voucher_no=voucher.voucher_no,
            account_code=account.code,
            account_name=account.name,
            summary=entry.summary,
            debit=entry.debit_amount,
            credit=entry.credit_amount,
        ))

    return JournalResponse(
        period={"year": period.year, "month": period.month},
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
    )


@report_router.get("/quantity-ledger/{account_id}", response_model=QuantityLedgerResponse)
async def quantity_ledger(
    account_id: UUID,
    period_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ledger:read")),
) -> QuantityLedgerResponse:
    """数量金额账 — quantity and amount ledger for inventory-type accounts."""
    from app.models.account import Account as AccountModel
    from app.models.period import AccountBalance, Period
    from app.schemas.report import QuantityLedgerRow

    # 1. Get account, verify is_quantity
    acct_result = await db.execute(
        select(AccountModel).where(AccountModel.id == account_id)
    )
    account = acct_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="科目不存在")
    if not account.is_quantity:
        raise HTTPException(status_code=400, detail="该科目未启用数量核算")

    # 2. Get period
    period_result = await db.execute(
        select(Period).where(Period.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    # 3. Query posted entries with quantity
    result = await db.execute(
        select(VoucherEntry, Voucher)
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .where(
            VoucherEntry.account_id == account_id,
            Voucher.period_id == period_id,
            Voucher.status == "posted",
            Voucher.deleted_at.is_(None),
        )
        .order_by(Voucher.date, Voucher.voucher_no, VoucherEntry.row_number)
    )

    rows: list[QuantityLedgerRow] = []
    qty_bal = Decimal("0")
    amt_bal = Decimal("0")
    opening_qty = Decimal("0")  # Could be tracked in a separate snapshot
    opening_amt = Decimal("0")

    for entry, voucher in result:
        qty = entry.quantity or Decimal("0")
        price = entry.price or Decimal("0")
        debit = entry.debit_amount
        credit = entry.credit_amount

        # Debit=increase(in), Credit=decrease(out) for inventory accounts
        if debit > 0:
            qty_in = qty
            amt_in = debit
            qty_out = Decimal("0")
            amt_out = Decimal("0")
        else:
            qty_in = Decimal("0")
            amt_in = Decimal("0")
            qty_out = qty
            amt_out = credit

        qty_bal = qty_bal + qty_in - qty_out
        amt_bal = amt_bal + amt_in - amt_out

        rows.append(QuantityLedgerRow(
            date=voucher.date,
            voucher_no=voucher.voucher_no,
            summary=entry.summary,
            quantity_in=qty_in,
            amount_in=amt_in,
            quantity_out=qty_out,
            amount_out=amt_out,
            quantity_balance=qty_bal,
            amount_balance=amt_bal,
        ))

    return QuantityLedgerResponse(
        period={"year": period.year, "month": period.month},
        account={"id": str(account.id), "code": account.code, "name": account.name},
        unit=account.quantity_unit or "",
        opening_quantity=opening_qty,
        opening_amount=opening_amt,
        rows=rows,
        closing_quantity=qty_bal,
        closing_amount=amt_bal,
    )


# ── Financial Statements (§3.7) ───────────────────────────────


@statement_router.get("/balance-sheet", response_model=BalanceSheetResponse)
async def balance_sheet(
    period_id: UUID = Query(...),
    template_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:read")),
) -> BalanceSheetResponse:
    """资产负债表 — balance sheet (§3.7).

    Returns a formatted balance sheet with current/non-current assets,
    current/non-current liabilities, and equity sections.
    """
    from app.models.period import AccountBalance, Period
    from app.models.account import Account as AccountModel

    # 1. Get period
    period_result = await db.execute(
        select(Period).where(Period.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    # 2. Get all enabled accounts with their balances for this period
    rows_result = await db.execute(
        select(AccountModel, AccountBalance)
        .outerjoin(
            AccountBalance,
            (AccountBalance.account_id == AccountModel.id)
            & (AccountBalance.period_id == period_id),
        )
        .where(AccountModel.is_enabled == True)
        .order_by(AccountModel.code)
    )
    rows = rows_result.all()

    # Build lookup: account_id -> (account, balance)
    balance_by_id: dict[str, tuple[AccountModel, AccountBalance | None]] = {}
    for acct, bal in rows:
        balance_by_id[str(acct.id)] = (acct, bal)

    # Track which account IDs have been assigned to specific items (for catch-all)
    assigned_ids: set[str] = set()

    # 3. Default template definition — standard Chinese balance sheet structure
    #    Each section has a side (assets/liabilities/equity) and items.
    #    Each item has code_prefixes for matching accounts.
    #    is_contra=True means the balance should be inverted (e.g., 累计折旧).
    template = {"name": "一般企业", "id": "default"}

    template_definition = [
        # ── Assets ──
        {
            "label": "流动资产",
            "side": "assets",
            "items": [
                {"name": "货币资金", "prefixes": ["1001", "1002", "1012"], "contra": False},
                {"name": "应收账款", "prefixes": ["1122"], "contra": False},
                {"name": "预付账款", "prefixes": ["1123"], "contra": False},
                {"name": "其他应收款", "prefixes": ["1221"], "contra": False},
                {"name": "存货", "prefixes": ["1403", "1405", "1406", "1407", "1408"], "contra": False},
                {"name": "其他流动资产", "prefixes": [], "contra": False, "catch_all": "asset_current"},
            ],
        },
        {
            "label": "非流动资产",
            "side": "assets",
            "items": [
                {"name": "固定资产", "prefixes": ["1601"], "contra": False},
                {"name": "累计折旧", "prefixes": ["1602"], "contra": True},
                {"name": "无形资产", "prefixes": ["1701"], "contra": False},
                {"name": "其他非流动资产", "prefixes": [], "contra": False, "catch_all": "asset_noncurrent"},
            ],
        },
        # ── Liabilities ──
        {
            "label": "流动负债",
            "side": "liabilities",
            "items": [
                {"name": "短期借款", "prefixes": ["2001"], "contra": False},
                {"name": "应付账款", "prefixes": ["2202"], "contra": False},
                {"name": "应付职工薪酬", "prefixes": ["2211"], "contra": False},
                {"name": "应交税费", "prefixes": ["2221"], "contra": False},
                {"name": "其他应付款", "prefixes": ["2241"], "contra": False},
                {"name": "其他流动负债", "prefixes": [], "contra": False, "catch_all": "liability_current"},
            ],
        },
        {
            "label": "非流动负债",
            "side": "liabilities",
            "items": [
                {"name": "长期借款", "prefixes": ["2501"], "contra": False},
                {"name": "其他非流动负债", "prefixes": [], "contra": False, "catch_all": "liability_noncurrent"},
            ],
        },
        # ── Equity ──
        {
            "label": "所有者权益",
            "side": "equity",
            "items": [
                {"name": "实收资本", "prefixes": ["4001"], "contra": False},
                {"name": "资本公积", "prefixes": ["4002"], "contra": False},
                {"name": "盈余公积", "prefixes": ["4101"], "contra": False},
                {"name": "未分配利润", "prefixes": ["4103", "4104"], "contra": False},
            ],
        },
    ]

    # 4. Helper: get net balance for a given side
    def _get_net(acct: AccountModel, bal: AccountBalance | None, side: str, is_contra: bool = False) -> dict:
        """Return {opening, closing} as net amounts from the perspective of the balance sheet side."""
        if bal is None:
            return {"opening": Decimal("0"), "closing": Decimal("0")}

        if side == "assets":
            # Assets: debit is positive
            closing = bal.closing_debit - bal.closing_credit
            opening = bal.opening_debit - bal.opening_credit
        else:
            # Liabilities & Equity: credit is positive
            closing = bal.closing_credit - bal.closing_debit
            opening = bal.opening_credit - bal.opening_debit

        if is_contra:
            closing = -closing
            opening = -opening

        return {"opening": opening, "closing": closing}

    # 5. Build result sections
    result_sections: list[StatementSection] = []
    totals_assets = {"opening": Decimal("0"), "closing": Decimal("0")}
    totals_liab_eq = {"opening": Decimal("0"), "closing": Decimal("0")}

    for tmpl_section in template_definition:
        section_items: list[StatementItem] = []
        section_subtotal = {"opening": Decimal("0"), "closing": Decimal("0")}

        for item_def in tmpl_section["items"]:
            item_opening = Decimal("0")
            item_closing = Decimal("0")

            prefixes = item_def.get("prefixes", [])
            catch_all = item_def.get("catch_all")
            is_contra = item_def.get("contra", False)

            if prefixes:
                # Match accounts by code prefix
                for aid, (acct, bal) in balance_by_id.items():
                    if aid in assigned_ids:
                        continue
                    if any(acct.code.startswith(p) for p in prefixes):
                        net = _get_net(acct, bal, tmpl_section["side"], is_contra)
                        item_opening += net["opening"]
                        item_closing += net["closing"]
                        assigned_ids.add(aid)
            elif catch_all:
                # Catch-all: match remaining unassigned accounts by type
                if catch_all == "asset_current":
                    type_filter = "asset"
                elif catch_all == "asset_noncurrent":
                    type_filter = "asset"
                elif catch_all == "liability_current":
                    type_filter = "liability"
                elif catch_all == "liability_noncurrent":
                    type_filter = "liability"
                else:
                    type_filter = None

                if type_filter:
                    for aid, (acct, bal) in balance_by_id.items():
                        if aid in assigned_ids:
                            continue
                        if acct.type != type_filter:
                            continue
                        # For catch-all current vs noncurrent, use code ranges
                        # Current assets: codes 1000-1599, Current liabilities: 2000-2499
                        acct_code_int = int(acct.code) if acct.code.isdigit() else 0
                        if catch_all == "asset_current" and acct_code_int >= 1600:
                            continue
                        if catch_all == "asset_noncurrent" and acct_code_int < 1600:
                            continue
                        if catch_all == "liability_current" and acct_code_int >= 2500:
                            continue
                        if catch_all == "liability_noncurrent" and acct_code_int < 2500:
                            continue
                        net = _get_net(acct, bal, tmpl_section["side"], is_contra)
                        item_opening += net["opening"]
                        item_closing += net["closing"]
                        assigned_ids.add(aid)

            section_items.append(StatementItem(
                name=item_def["name"],
                closing=item_closing,
                opening=item_opening,
            ))
            section_subtotal["opening"] += item_opening
            section_subtotal["closing"] += item_closing

        result_sections.append(StatementSection(
            label=tmpl_section["label"],
            items=section_items,
            subtotal={
                "closing": str(section_subtotal["closing"]),
                "opening": str(section_subtotal["opening"]),
            },
        ))

        if tmpl_section["side"] == "assets":
            totals_assets["opening"] += section_subtotal["opening"]
            totals_assets["closing"] += section_subtotal["closing"]
        else:
            totals_liab_eq["opening"] += section_subtotal["opening"]
            totals_liab_eq["closing"] += section_subtotal["closing"]

    # 6. Revenue/Expense accounts roll into 未分配利润 (retained earnings)
    #    Find the 未分配利润 item and add net profit/loss
    net_profit = Decimal("0")
    for aid, (acct, bal) in balance_by_id.items():
        if aid in assigned_ids:
            continue
        if acct.type in ("revenue", "expense"):
            if bal is None:
                continue
            # Revenue: credit > debit → profit; Expense: debit > credit → loss
            if acct.dc_type == "C":
                net_profit += bal.closing_credit - bal.closing_debit
            else:
                net_profit -= bal.closing_debit - bal.closing_credit
            assigned_ids.add(aid)

    # Add net profit to 未分配利润 (last item in last section)
    if result_sections:
        last_section = result_sections[-1]
        for item in last_section.items:
            if item.name == "未分配利润":
                item.closing += net_profit
                # Update subtotal
                subtotal = last_section.subtotal
                subtotal["closing"] = str(
                    Decimal(subtotal["closing"]) + net_profit
                )
                totals_liab_eq["closing"] += net_profit
                break

    # 7. Return response
    return BalanceSheetResponse(
        period={"year": period.year, "month": period.month},
        template=template,
        sections=result_sections,
        totals={
            "assets": {
                "closing": str(totals_assets["closing"]),
                "opening": str(totals_assets["opening"]),
            },
            "liabilities_equity": {
                "closing": str(totals_liab_eq["closing"]),
                "opening": str(totals_liab_eq["opening"]),
            },
        },
    )


@statement_router.get("/income", response_model=IncomeStatementResponse)
async def income_statement(
    period_id: UUID = Query(...),
    template_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:read")),
) -> IncomeStatementResponse:
    """利润表 — income / profit & loss statement (§3.7).

    Computes: 营业收入 → 营业利润 → 利润总额 → 净利润.
    Shows current period and cumulative (year-to-date) amounts.
    """
    from app.models.period import AccountBalance, Period
    from app.models.account import Account as AccountModel

    # 1. Get period
    period_result = await db.execute(
        select(Period).where(Period.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    # 2. Get all enabled revenue/expense accounts with balances for this period
    rows_result = await db.execute(
        select(AccountModel, AccountBalance)
        .outerjoin(
            AccountBalance,
            (AccountBalance.account_id == AccountModel.id)
            & (AccountBalance.period_id == period_id),
        )
        .where(
            AccountModel.is_enabled == True,
            AccountModel.type.in_(["revenue", "expense"]),
        )
        .order_by(AccountModel.code)
    )
    rows = rows_result.all()

    template = {"name": "一般企业", "id": "default"}

    # Build account->balance lookup
    balance_map: dict[str, tuple[AccountModel, AccountBalance | None]] = {}
    for acct, bal in rows:
        balance_map[str(acct.id)] = (acct, bal)

    assigned_ids: set[str] = set()

    # 3. 本期金额 (current period only) — this period's activity (current_*).
    #    revenue → positive (credit side), expense → positive on debit side.
    def _net_amount(acct: AccountModel, bal: AccountBalance | None) -> Decimal:
        if bal is None:
            return Decimal("0")
        if acct.type == "revenue":
            return bal.current_credit - bal.current_debit
        else:  # expense
            return bal.current_debit - bal.current_credit

    # 本年累计 (year-to-date) — opening (prior periods this year) + current = closing.
    def _cumulative_amount(acct: AccountModel, bal: AccountBalance | None) -> Decimal:
        if bal is None:
            return Decimal("0")
        if acct.type == "revenue":
            return bal.closing_credit - bal.closing_debit
        else:
            return bal.closing_debit - bal.closing_credit

    # 4. Template definition
    income_template = [
        {
            "label": "一、营业收入",
            "items": [
                {
                    "name": "营业收入",
                    "prefixes": ["6001"],
                    "sign": 1,
                },  # 主营业务收入
                {
                    "name": "其他业务收入",
                    "prefixes": ["6051"],
                    "sign": 1,
                },
            ],
        },
        {
            "label": "减：营业成本",
            "items": [
                {
                    "name": "营业成本",
                    "prefixes": ["6401"],
                    "sign": -1,
                },  # 主营业务成本
                {
                    "name": "其他业务成本",
                    "prefixes": ["6402"],
                    "sign": -1,
                },
                {
                    "name": "税金及附加",
                    "prefixes": ["6403"],
                    "sign": -1,
                },
                {
                    "name": "销售费用",
                    "prefixes": ["6601"],
                    "sign": -1,
                },
                {
                    "name": "管理费用",
                    "prefixes": ["6602"],
                    "sign": -1,
                },
                {
                    "name": "财务费用",
                    "prefixes": ["6603"],
                    "sign": -1,
                },
                {
                    "name": "信用减值损失",
                    "prefixes": ["6701"],
                    "sign": -1,
                },
                {
                    "name": "其他费用",
                    "prefixes": [],
                    "sign": -1,
                    "catch_all": "expense",
                },
            ],
        },
        {
            "label": "加：其他收益",
            "items": [
                {
                    "name": "投资收益",
                    "prefixes": ["6111"],
                    "sign": 1,
                },
                {
                    "name": "公允价值变动收益",
                    "prefixes": ["6101"],
                    "sign": 1,
                },
                {
                    "name": "营业外收入",
                    "prefixes": ["6301"],
                    "sign": 1,
                },
                {
                    "name": "其他收益",
                    "prefixes": [],
                    "sign": 1,
                    "catch_all": "revenue",
                },
            ],
        },
        {
            "label": "减：营业外支出",
            "items": [
                {
                    "name": "营业外支出",
                    "prefixes": ["6711"],
                    "sign": -1,
                },
            ],
        },
        {
            "label": "减：所得税费用",
            "items": [
                {
                    "name": "所得税费用",
                    "prefixes": ["6801"],
                    "sign": -1,
                },
            ],
        },
    ]

    # 5. Build result
    result_sections: list[StatementSection] = []
    running_total_current = Decimal("0")
    running_total_cumulative = Decimal("0")
    # Stage totals for key subtotals
    revenue_total = Decimal("0")
    revenue_cumulative = Decimal("0")

    for tmpl_section in income_template:
        section_items: list[StatementItem] = []
        section_current = Decimal("0")
        section_cumulative = Decimal("0")

        for item_def in tmpl_section["items"]:
            item_current = Decimal("0")
            item_cumulative = Decimal("0")
            prefixes = item_def.get("prefixes", [])
            catch_all = item_def.get("catch_all")
            sign = item_def.get("sign", 1)

            if prefixes:
                for aid, (acct, bal) in balance_map.items():
                    if aid in assigned_ids:
                        continue
                    if any(acct.code.startswith(p) for p in prefixes):
                        amt = _net_amount(acct, bal)
                        cum = _cumulative_amount(acct, bal)
                        item_current += amt
                        item_cumulative += cum
                        assigned_ids.add(aid)
            elif catch_all:
                for aid, (acct, bal) in balance_map.items():
                    if aid in assigned_ids:
                        continue
                    if catch_all == "expense" and acct.type != "expense":
                        continue
                    if catch_all == "revenue" and acct.type != "revenue":
                        continue
                    amt = _net_amount(acct, bal)
                    cum = _cumulative_amount(acct, bal)
                    item_current += amt
                    item_cumulative += cum
                    assigned_ids.add(aid)

            # Apply sign: revenue items already positive, expense items already negative
            # sign indicates whether this is an add(+) or subtract(-) line in the P&L
            display_current = item_current * sign if sign == 1 else abs(item_current) * sign
            display_cumulative = item_cumulative * sign if sign == 1 else abs(item_cumulative) * sign

            section_items.append(StatementItem(
                name=item_def["name"],
                closing=display_current,
                opening=display_cumulative,
            ))
            section_current += display_current
            section_cumulative += display_cumulative

        running_total_current += section_current
        running_total_cumulative += section_cumulative

        # Track revenue subtotal for display
        if tmpl_section["label"] == "一、营业收入":
            revenue_total = section_current
            revenue_cumulative = section_cumulative

        result_sections.append(StatementSection(
            label=tmpl_section["label"],
            items=section_items,
            subtotal={
                "closing": str(section_current),
                "opening": str(section_cumulative),
            },
        ))

    # 6. Compute key totals: 营业利润, 利润总额, 净利润
    # These are running totals from the sections
    net_profit_current = running_total_current
    net_profit_cumulative = running_total_cumulative

    totals = {
        "revenue": {
            "closing": str(revenue_total),
            "opening": str(revenue_cumulative),
        },
        "operating_profit": {
            "closing": str(
                revenue_total
                + sum(
                    Decimal(s.subtotal["closing"]) for s in result_sections
                    if "营业成本" in s.label
                )
            ),
            "opening": str(
                revenue_cumulative
                + sum(
                    Decimal(s.subtotal["opening"]) for s in result_sections
                    if "营业成本" in s.label
                )
            ),
        },
        "net_profit": {
            "closing": str(net_profit_current),
            "opening": str(net_profit_cumulative),
        },
    }

    return IncomeStatementResponse(
        period={"year": period.year, "month": period.month},
        template=template,
        sections=result_sections,
        totals=totals,
    )


@statement_router.get("/cash-flow", response_model=CashFlowStatementResponse)
async def cash_flow(
    period_id: UUID = Query(...),
    template_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:read")),
) -> CashFlowStatementResponse:
    """现金流量表 — cash flow statement (§3.7).

    Computes cash inflows/outflows from cash account movements in the period.
    Sections: operating, investing, financing activities.
    """
    from app.models.period import AccountBalance, Period
    from app.models.account import Account as AccountModel

    # 1. Get period
    period_result = await db.execute(
        select(Period).where(Period.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    template = {"name": "一般企业", "id": "default"}

    # 2. Get all cash-type accounts (is_cash=True) with their current-period activity
    cash_result = await db.execute(
        select(AccountModel, AccountBalance)
        .outerjoin(
            AccountBalance,
            (AccountBalance.account_id == AccountModel.id)
            & (AccountBalance.period_id == period_id),
        )
        .where(
            AccountModel.is_enabled == True,
            AccountModel.is_cash == True,
        )
        .order_by(AccountModel.code)
    )
    cash_rows = cash_result.all()

    # 3. Cash flow = net cash change = current_debit - current_credit for debit-type accounts
    #    For credit-type accounts (unlikely for cash): current_credit - current_debit
    total_cash_in = Decimal("0")
    total_cash_out = Decimal("0")

    for acct, bal in cash_rows:
        if bal is None:
            continue
        # Cash accounts are debit-type. Debit = inflow, Credit = outflow.
        total_cash_in += bal.current_debit
        total_cash_out += bal.current_credit

    net_cash_flow = total_cash_in - total_cash_out

    # 4. Get detailed cash entries by voucher to categorize
    #    Query posted voucher entries for cash accounts this period
    from app.models.voucher import Voucher as VoucherModel, VoucherEntry as VoucherEntryModel

    entry_result = await db.execute(
        select(VoucherEntryModel, VoucherModel)
        .join(VoucherModel, VoucherEntryModel.voucher_id == VoucherModel.id)
        .join(AccountModel, VoucherEntryModel.account_id == AccountModel.id)
        .where(
            VoucherModel.period_id == period_id,
            VoucherModel.status == "posted",
            VoucherModel.deleted_at.is_(None),
            AccountModel.is_cash == True,
        )
        .order_by(VoucherModel.date, VoucherModel.voucher_no)
    )

    # 5. Categorize entries using summary keywords and account patterns
    operating_in = Decimal("0")
    operating_out = Decimal("0")
    investing_in = Decimal("0")
    investing_out = Decimal("0")
    financing_in = Decimal("0")
    financing_out = Decimal("0")

    for entry, voucher in entry_result:
        summary = (entry.summary or "").lower()
        debit = entry.debit_amount or Decimal("0")
        credit = entry.credit_amount or Decimal("0")

        # Determine category from summary keywords
        # Investing: 固定资产, 无形资产, 投资, 资产购置, 资产出售
        # Financing: 借款, 贷款, 分红, 股利, 资本, 发行股票, 偿还借款
        # Operating: everything else (sales, purchases, salaries, taxes, etc.)
        invest_keywords = [
            "固定资产", "无形资产", "投资", "资产购置", "资产出售",
            "设备", "房产", "土地", "在建工程", "处置",
        ]
        finance_keywords = [
            "借款", "贷款", "分红", "股利", "资本", "发行",
            "偿还借款", "偿还贷款", "利息支出", "融资",
        ]

        is_investing = any(kw in entry.summary for kw in invest_keywords)
        is_financing = any(kw in entry.summary for kw in finance_keywords)

        if is_investing:
            investing_in += debit
            investing_out += credit
        elif is_financing:
            financing_in += debit
            financing_out += credit
        else:
            operating_in += debit
            operating_out += credit

    # 6. Build statement sections
    def _make_section(
        label: str, items: list[tuple[str, Decimal]]
    ) -> StatementSection:
        section_items = [
            StatementItem(
                name=name, closing=amt, opening=Decimal("0")
            )
            for name, amt in items
        ]
        subtotal = sum((item.closing for item in section_items), Decimal("0"))
        return StatementSection(
            label=label,
            items=section_items,
            subtotal={
                "closing": str(subtotal),
                "opening": "0",
            },
        )

    sections = [
        _make_section(
            "一、经营活动产生的现金流量",
            [
                ("销售商品、提供劳务收到的现金", operating_in),
                ("购买商品、接受劳务支付的现金", -operating_out),
            ],
        ),
        _make_section(
            "二、投资活动产生的现金流量",
            [
                ("收回投资收到的现金", investing_in),
                ("购建固定资产、无形资产支付的现金", -investing_out),
            ],
        ),
        _make_section(
            "三、筹资活动产生的现金流量",
            [
                ("取得借款收到的现金", financing_in),
                ("偿还债务支付的现金", -financing_out),
            ],
        ),
    ]

    totals = {
        "operating": {
            "closing": str(operating_in - operating_out),
            "opening": "0",
        },
        "investing": {
            "closing": str(investing_in - investing_out),
            "opening": "0",
        },
        "financing": {
            "closing": str(financing_in - financing_out),
            "opening": "0",
        },
        "net_increase": {
            "closing": str(net_cash_flow),
            "opening": "0",
        },
    }

    return CashFlowStatementResponse(
        period={"year": period.year, "month": period.month},
        template=template,
        sections=sections,
        totals=totals,
    )


@statement_router.get("/templates")
async def statement_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:read")),
) -> list[dict]:
    """List available financial statement templates."""
    return [
        {
            "id": "default",
            "name": "一般企业",
            "type": "balance_sheet",
            "description": "适用于一般企业的标准资产负债表模板",
        },
        {
            "id": "default",
            "name": "一般企业",
            "type": "income",
            "description": "适用于一般企业的标准利润表模板",
        },
        {
            "id": "default",
            "name": "一般企业",
            "type": "cash_flow",
            "description": "适用于一般企业的标准现金流量表模板",
        },
        {
            "id": "small_business",
            "name": "小企业",
            "type": "balance_sheet",
            "description": "适用于小企业的简化资产负债表模板",
        },
        {
            "id": "small_business",
            "name": "小企业",
            "type": "income",
            "description": "适用于小企业的简化利润表模板",
        },
    ]


@statement_router.post("/export")
async def export_statement(
    body: StatementExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:export")),
):
    """Export a financial statement as Excel.

    Body: {type: 'balance_sheet'|'income'|'cash_flow', period_id, format: 'excel'}
    """
    from io import BytesIO
    from fastapi.responses import StreamingResponse

    # 1. Generate the statement data by calling the existing endpoint logic
    if body.type == "balance_sheet":
        statement_data = await balance_sheet(
            period_id=body.period_id,
            template_id=None,
            db=db,
            current_user=current_user,
        )
        title = "资产负债表"
    elif body.type == "income":
        statement_data = await income_statement(
            period_id=body.period_id,
            template_id=None,
            db=db,
            current_user=current_user,
        )
        title = "利润表"
    elif body.type == "cash_flow":
        statement_data = await cash_flow(
            period_id=body.period_id,
            template_id=None,
            db=db,
            current_user=current_user,
        )
        title = "现金流量表"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown statement type: {body.type}")

    # 2. Build Excel workbook
    if body.format == "excel":
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="openpyxl not installed. Run: pip install openpyxl",
            )

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = title

        # Styles
        title_font = Font(name="微软雅黑", size=16, bold=True)
        header_font = Font(name="微软雅黑", size=10, bold=True)
        normal_font = Font(name="微软雅黑", size=10)
        bold_font = Font(name="微软雅黑", size=10, bold=True)
        center_align = Alignment(horizontal="center", vertical="center")
        right_align = Alignment(horizontal="right", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )
        header_fill = PatternFill(start_color="F0F0F0", end_color="F0F0F0", fill_type="solid")
        subtotal_fill = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")

        row = 1

        # Title
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        cell = ws.cell(row=row, column=1, value=title)
        cell.font = title_font
        cell.alignment = center_align
        row += 1

        # Period info
        period = statement_data.period
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        cell = ws.cell(
            row=row, column=1,
            value=f"{period['year']}年{period['month']}月 | 单位：元",
        )
        cell.font = normal_font
        cell.alignment = center_align
        row += 1
        row += 1  # blank row

        # Build based on statement type
        if body.type == "balance_sheet":
            _export_balance_sheet_excel(ws, row, statement_data)
        elif body.type == "income":
            _export_income_excel(ws, row, statement_data)
        elif body.type == "cash_flow":
            _export_cash_flow_excel(ws, row, statement_data)

        # Save to buffer
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        filename = f"{title}_{period['year']}{period['month']:02d}.xlsx"
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    elif body.format == "pdf":
        raise HTTPException(
            status_code=501,
            detail="PDF export not yet supported. Use Excel format.",
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {body.format}")


# ── Excel Export Helpers ───────────────────────────────────────


def _export_balance_sheet_excel(ws, start_row: int, data: BalanceSheetResponse) -> int:
    """Write balance sheet data to Excel worksheet. Returns final row."""
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

    normal_font = Font(name="微软雅黑", size=10)
    bold_font = Font(name="微软雅黑", size=10, bold=True)
    header_font = Font(name="微软雅黑", size=10, bold=True)
    right_align = Alignment(horizontal="right", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    header_fill = PatternFill(start_color="F0F0F0", end_color="F0F0F0", fill_type="solid")
    subtotal_fill = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")

    row = start_row

    # Column headers
    for col, (text, width) in enumerate(
        [("项目", 30), ("期末余额", 18), ("期初余额", 18)], 1
    ):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
        ws.column_dimensions[cell.column_letter].width = width
    row += 1

    def _fmt(v):
        try:
            return f"{float(v):,.2f}"
        except (ValueError, TypeError):
            return str(v) if v else ""

    for section in data.sections:
        # Section header
        cell = ws.cell(row=row, column=1, value=section.label)
        cell.font = bold_font
        cell.fill = subtotal_fill
        cell.border = thin_border
        for c in (2, 3):
            ws.cell(row=row, column=c).fill = subtotal_fill
            ws.cell(row=row, column=c).border = thin_border
        row += 1

        # Items
        for item in section.items:
            ws.cell(row=row, column=1, value=f"  {item.name}").font = normal_font
            ws.cell(row=row, column=1).alignment = left_align
            ws.cell(row=row, column=1).border = thin_border

            cell2 = ws.cell(row=row, column=2, value=_fmt(item.closing))
            cell2.font = normal_font
            cell2.alignment = right_align
            cell2.border = thin_border

            cell3 = ws.cell(row=row, column=3, value=_fmt(item.opening))
            cell3.font = normal_font
            cell3.alignment = right_align
            cell3.border = thin_border
            row += 1

        # Section subtotal
        cell = ws.cell(row=row, column=1, value=f"  {section.label}合计")
        cell.font = bold_font
        cell.border = thin_border
        cell2 = ws.cell(row=row, column=2, value=_fmt(section.subtotal["closing"]))
        cell2.font = bold_font
        cell2.alignment = right_align
        cell2.border = thin_border
        cell3 = ws.cell(row=row, column=3, value=_fmt(section.subtotal["opening"]))
        cell3.font = bold_font
        cell3.alignment = right_align
        cell3.border = thin_border
        row += 1

    # Totals
    row += 1
    for label, key in [("资产总计", "assets"), ("负债及所有者权益总计", "liabilities_equity")]:
        cell = ws.cell(row=row, column=1, value=label)
        cell.font = Font(name="微软雅黑", size=10, bold=True)
        cell.border = thin_border
        cell2 = ws.cell(row=row, column=2, value=_fmt(data.totals[key]["closing"]))
        cell2.font = Font(name="微软雅黑", size=10, bold=True)
        cell2.alignment = right_align
        cell2.border = thin_border
        cell3 = ws.cell(row=row, column=3, value=_fmt(data.totals[key]["opening"]))
        cell3.font = Font(name="微软雅黑", size=10, bold=True)
        cell3.alignment = right_align
        cell3.border = thin_border
        row += 1

    return row


def _export_income_excel(ws, start_row: int, data: IncomeStatementResponse) -> int:
    """Write income statement data to Excel worksheet."""
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

    normal_font = Font(name="微软雅黑", size=10)
    bold_font = Font(name="微软雅黑", size=10, bold=True)
    header_font = Font(name="微软雅黑", size=10, bold=True)
    right_align = Alignment(horizontal="right", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    header_fill = PatternFill(start_color="F0F0F0", end_color="F0F0F0", fill_type="solid")
    subtotal_fill = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")

    row = start_row

    for col, (text, width) in enumerate(
        [("项目", 30), ("本期金额", 18), ("本年累计", 18)], 1
    ):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
        ws.column_dimensions[cell.column_letter].width = width
    row += 1

    def _fmt(v):
        try:
            return f"{float(v):,.2f}"
        except (ValueError, TypeError):
            return str(v) if v else ""

    for section in data.sections:
        # Section header
        cell = ws.cell(row=row, column=1, value=section.label)
        cell.font = bold_font
        cell.fill = subtotal_fill
        for c in (1, 2, 3):
            ws.cell(row=row, column=c).border = thin_border
        row += 1

        for item in section.items:
            ws.cell(row=row, column=1, value=f"  {item.name}").font = normal_font
            ws.cell(row=row, column=1).alignment = left_align
            ws.cell(row=row, column=1).border = thin_border

            cell2 = ws.cell(row=row, column=2, value=_fmt(item.closing))
            cell2.font = normal_font
            cell2.alignment = right_align
            cell2.border = thin_border

            cell3 = ws.cell(row=row, column=3, value=_fmt(item.opening))
            cell3.font = normal_font
            cell3.alignment = right_align
            cell3.border = thin_border
            row += 1

        # Subtotal
        cell = ws.cell(row=row, column=1, value="  小计")
        cell.font = bold_font
        cell.border = thin_border
        cell2 = ws.cell(row=row, column=2, value=_fmt(section.subtotal["closing"]))
        cell2.font = bold_font
        cell2.alignment = right_align
        cell2.border = thin_border
        cell3 = ws.cell(row=row, column=3, value=_fmt(section.subtotal["opening"]))
        cell3.font = bold_font
        cell3.alignment = right_align
        cell3.border = thin_border
        row += 1

    # Net profit
    row += 1
    totals = data.totals
    if totals and "net_profit" in totals:
        cell = ws.cell(row=row, column=1, value="四、净利润")
        cell.font = Font(name="微软雅黑", size=10, bold=True)
        cell.border = thin_border
        cell2 = ws.cell(row=row, column=2, value=_fmt(totals["net_profit"]["closing"]))
        cell2.font = Font(name="微软雅黑", size=10, bold=True)
        cell2.alignment = right_align
        cell2.border = thin_border
        cell3 = ws.cell(row=row, column=3, value=_fmt(totals["net_profit"]["opening"]))
        cell3.font = Font(name="微软雅黑", size=10, bold=True)
        cell3.alignment = right_align
        cell3.border = thin_border
        row += 1

    return row


def _export_cash_flow_excel(ws, start_row: int, data: CashFlowStatementResponse) -> int:
    """Write cash flow statement data to Excel worksheet."""
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

    normal_font = Font(name="微软雅黑", size=10)
    bold_font = Font(name="微软雅黑", size=10, bold=True)
    header_font = Font(name="微软雅黑", size=10, bold=True)
    right_align = Alignment(horizontal="right", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    header_fill = PatternFill(start_color="F0F0F0", end_color="F0F0F0", fill_type="solid")
    subtotal_fill = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")

    row = start_row

    for col, (text, width) in enumerate(
        [("项目", 40), ("本期金额", 18)], 1
    ):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
        ws.column_dimensions[cell.column_letter].width = width
    row += 1

    def _fmt(v):
        try:
            return f"{float(v):,.2f}"
        except (ValueError, TypeError):
            return str(v) if v else ""

    for section in data.sections:
        cell = ws.cell(row=row, column=1, value=section.label)
        cell.font = bold_font
        cell.fill = subtotal_fill
        for c in (1, 2):
            ws.cell(row=row, column=c).border = thin_border
        row += 1

        for item in section.items:
            ws.cell(row=row, column=1, value=f"  {item.name}").font = normal_font
            ws.cell(row=row, column=1).alignment = left_align
            ws.cell(row=row, column=1).border = thin_border

            cell2 = ws.cell(row=row, column=2, value=_fmt(item.closing))
            cell2.font = normal_font
            cell2.alignment = right_align
            cell2.border = thin_border
            row += 1

        cell = ws.cell(row=row, column=1, value=f"  {section.label.replace('产生的现金流量', '现金流量净额')}")
        cell.font = bold_font
        cell.border = thin_border
        cell2 = ws.cell(row=row, column=2, value=_fmt(section.subtotal["closing"]))
        cell2.font = bold_font
        cell2.alignment = right_align
        cell2.border = thin_border
        row += 1

    # Net increase
    row += 1
    totals = data.totals
    if totals and "net_increase" in totals:
        cell = ws.cell(row=row, column=1, value="现金及现金等价物净增加额")
        cell.font = Font(name="微软雅黑", size=10, bold=True)
        cell.border = thin_border
        cell2 = ws.cell(row=row, column=2, value=_fmt(totals["net_increase"]["closing"]))
        cell2.font = Font(name="微软雅黑", size=10, bold=True)
        cell2.alignment = right_align
        cell2.border = thin_border
        row += 1

    return row
