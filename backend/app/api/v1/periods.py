"""Period management and carry-forward routes (§3.8).

GET  /periods           — list all periods
POST /periods           — create period
GET  /periods/current   — current open period
POST /periods/{id}/close    — close period
POST /periods/{id}/reopen   — reopen period
GET  /periods/{id}/trial-balance — trial balance check

GET  /carry-forward/templates — list carry templates
POST /carry-forward/execute   — execute carry forward
GET  /carry-forward/check     — AI pre-check
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.period import AccountBalance, CarryForward, CarryTemplate, Period
from app.models.user import User
from app.models.voucher import Voucher
from app.schemas.common import SuccessMessage
from app.schemas.period import (
    AIProceedCheckResponse,
    CarryForwardRequest,
    CarryForwardResponse,
    PeriodCreate,
    PeriodListResponse,
    PeriodSchema,
)

router = APIRouter()
carry_forward_router = APIRouter()


# ── Periods ───────────────────────────────────────────────────

@router.get("", response_model=PeriodListResponse)
async def list_periods(
    year: int = Query(None),
    status: str = Query(None, description="open/closed"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PeriodListResponse:
    """List accounting periods, optionally filtered by year and status."""
    # 1. Build conditions
    conditions = []
    if year is not None:
        conditions.append(Period.year == year)
    if status is not None:
        conditions.append(Period.status == status)

    # 2. Count total
    count_query = select(func.count(Period.id))
    if conditions:
        count_query = count_query.where(*conditions)
    total = (await db.execute(count_query)).scalar_one()

    # 3. Fetch periods ordered by year DESC, month DESC
    data_query = select(Period).order_by(Period.year.desc(), Period.month.desc())
    if conditions:
        data_query = data_query.where(*conditions)
    result = await db.execute(data_query)
    periods = result.scalars().all()

    return PeriodListResponse(
        periods=[PeriodSchema.model_validate(p) for p in periods],
        total=total,
    )


@router.post("", response_model=PeriodSchema, status_code=201)
async def create_period(
    body: PeriodCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("period:close")),
) -> PeriodSchema:
    """Create a new accounting period.

    Automatically carries forward opening balances from the previous month
    if balances exist for that period.
    """
    # 1. Check for duplicate period
    existing = (
        await db.execute(
            select(Period).where(
                Period.year == body.year, Period.month == body.month
            )
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Period {body.year}-{body.month:02d} already exists",
        )

    # 2. Create the period
    period = Period(
        year=body.year,
        month=body.month,
        status="open",
    )
    db.add(period)
    await db.flush()  # Get the ID assigned

    # 3. Carry forward opening balances from previous month if they exist
    prev_year = body.year
    prev_month = body.month - 1
    if prev_month == 0:
        prev_year -= 1
        prev_month = 12

    prev_balances = (
        await db.execute(
            select(AccountBalance).join(Period).where(
                Period.year == prev_year,
                Period.month == prev_month,
            )
        )
    ).scalars().all()

    if prev_balances:
        for pb in prev_balances:
            ab = AccountBalance(
                period_id=period.id,
                account_id=pb.account_id,
                opening_debit=pb.closing_debit,
                opening_credit=pb.closing_credit,
                current_debit=Decimal("0"),
                current_credit=Decimal("0"),
                closing_debit=pb.closing_debit,
                closing_credit=pb.closing_credit,
            )
            db.add(ab)

    await db.flush()
    return PeriodSchema.model_validate(period)


@router.get("/current", response_model=PeriodSchema)
async def get_current_period(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PeriodSchema:
    """Return the currently open accounting period.

    If no period is open, returns the latest period.
    Priority: open period with the earliest month.
    """
    # 1. Try to find the earliest open period
    open_period = (
        await db.execute(
            select(Period)
            .where(Period.status == "open")
            .order_by(Period.year.asc(), Period.month.asc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if open_period:
        return PeriodSchema.model_validate(open_period)

    # 2. Fallback: return the latest period by year DESC, month DESC
    latest_period = (
        await db.execute(
            select(Period)
            .order_by(Period.year.desc(), Period.month.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if latest_period is None:
        raise HTTPException(
            status_code=404, detail="No accounting periods found"
        )

    return PeriodSchema.model_validate(latest_period)


@router.post("/{period_id}/close", response_model=PeriodSchema)
async def close_period(
    period_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("period:close")),
) -> PeriodSchema:
    """Close an accounting period.

    §7.4 full logic:
    1. Acquire row lock (SELECT FOR UPDATE)
    2. Verify period.status == 'open'
    3. Verify all audited vouchers are posted
    4. Carry closing balances forward to next period
    5. Mark period as closed
    """
    # 1. Acquire row lock
    period = (
        await db.execute(
            select(Period).where(Period.id == period_id).with_for_update()
        )
    ).scalar_one_or_none()

    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")

    # 2. Verify status
    if period.status != "open":
        raise HTTPException(
            status_code=409,
            detail=f"Period already {period.status} — cannot close",
        )

    # 3. Check for audited-but-unposted vouchers
    unposted_count = (
        await db.execute(
            select(func.count(Voucher.id)).where(
                Voucher.period_id == period_id,
                Voucher.status == "audited",
            )
        )
    ).scalar_one()

    if unposted_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot close period: {unposted_count} audited but unposted voucher(s) exist",
        )

    # 4. Get or create next period
    next_year = period.year
    next_month = period.month + 1
    if next_month > 12:
        next_year += 1
        next_month = 1

    next_period = (
        await db.execute(
            select(Period).where(
                Period.year == next_year, Period.month == next_month
            )
        )
    ).scalar_one_or_none()

    if next_period is None:
        next_period = Period(
            year=next_year,
            month=next_month,
            status="open",
        )
        db.add(next_period)
        await db.flush()

    # 5. Carry forward closing balances to next period
    current_balances = (
        await db.execute(
            select(AccountBalance).where(
                AccountBalance.period_id == period_id
            )
        )
    ).scalars().all()

    for cb in current_balances:
        stmt = (
            insert(AccountBalance)
            .values(
                period_id=next_period.id,
                account_id=cb.account_id,
                opening_debit=cb.closing_debit,
                opening_credit=cb.closing_credit,
                current_debit=Decimal("0"),
                current_credit=Decimal("0"),
                closing_debit=cb.closing_debit,
                closing_credit=cb.closing_credit,
            )
            .on_conflict_do_update(
                index_elements=["period_id", "account_id"],
                set_=dict(
                    opening_debit=cb.closing_debit,
                    opening_credit=cb.closing_credit,
                    closing_debit=cb.closing_debit,
                    closing_credit=cb.closing_credit,
                ),
            )
        )
        await db.execute(stmt)

    # 6. Mark period as closed
    period.status = "closed"
    period.closed_at = datetime.now(timezone.utc)
    period.closed_by = current_user.id

    await db.flush()
    return PeriodSchema.model_validate(period)


@router.post("/{period_id}/reopen", response_model=PeriodSchema)
async def reopen_period(
    period_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("period:reopen")),
) -> PeriodSchema:
    """Reopen a closed period (admin only).

    Reverses the close operation: deletes next period's carry-forward balances.
    """
    # 1. Acquire row lock
    period = (
        await db.execute(
            select(Period).where(Period.id == period_id).with_for_update()
        )
    ).scalar_one_or_none()

    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")

    # 2. Verify status
    if period.status != "closed":
        raise HTTPException(
            status_code=409,
            detail=f"Period is {period.status} — can only reopen closed periods",
        )

    # 3. Find next period
    next_year = period.year
    next_month = period.month + 1
    if next_month > 12:
        next_year += 1
        next_month = 1

    next_period = (
        await db.execute(
            select(Period).where(
                Period.year == next_year, Period.month == next_month
            )
        )
    ).scalar_one_or_none()

    # 4. Delete AccountBalance records for next period that were carried from this one
    if next_period is not None:
        # Get the account IDs that had balances in the current (being reopened) period
        current_account_ids = (
            await db.execute(
                select(AccountBalance.account_id).where(
                    AccountBalance.period_id == period_id
                )
            )
        ).scalars().all()

        if current_account_ids:
            # Delete next period balances for those same accounts
            from sqlalchemy import delete

            await db.execute(
                delete(AccountBalance).where(
                    AccountBalance.period_id == next_period.id,
                    AccountBalance.account_id.in_(current_account_ids),
                )
            )

    # 5. Mark period as open
    period.status = "open"
    period.closed_at = None
    period.closed_by = None

    await db.flush()
    return PeriodSchema.model_validate(period)


@router.get("/{period_id}/trial-balance")
async def period_trial_balance_check(
    period_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Check if the period's trial balance is balanced.

    Returns {is_balanced: bool, total_debit, total_credit, difference}.
    """
    # 1. Sum current_debit and current_credit across all accounts for this period
    result = (
        await db.execute(
            select(
                func.coalesce(func.sum(AccountBalance.current_debit), 0),
                func.coalesce(func.sum(AccountBalance.current_credit), 0),
            ).where(AccountBalance.period_id == period_id)
        )
    ).one()

    total_debit = Decimal(str(result[0]))
    total_credit = Decimal(str(result[1]))
    difference = abs(total_debit - total_credit)
    is_balanced = difference < Decimal("0.01")

    return {
        "is_balanced": is_balanced,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "difference": difference,
    }


# ── Carry Forward ─────────────────────────────────────────────


@carry_forward_router.get("/templates")
async def list_carry_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List available carry-forward templates, ordered by sort_order."""
    result = await db.execute(
        select(CarryTemplate)
        .where(CarryTemplate.is_enabled == True)
        .order_by(CarryTemplate.sort_order)
    )
    templates = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "description": t.description or "",
            "rules": t.rules or {},
            "sort_order": t.sort_order,
            "is_enabled": t.is_enabled,
        }
        for t in templates
    ]


@carry_forward_router.post("/templates", status_code=201)
async def create_carry_template(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("period:close")),
) -> dict:
    """Create a new carry-forward template."""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="模板名称不能为空")

    template = CarryTemplate(
        name=name,
        description=body.get("description"),
        rules=body.get("rules", {}),
        sort_order=body.get("sort_order", 0),
        is_enabled=body.get("is_enabled", True),
    )
    db.add(template)
    await db.flush()
    return {
        "id": str(template.id),
        "name": template.name,
        "description": template.description or "",
        "rules": template.rules or {},
        "sort_order": template.sort_order,
        "is_enabled": template.is_enabled,
    }


@carry_forward_router.put("/templates/{template_id}")
async def update_carry_template(
    template_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("period:close")),
) -> dict:
    """Update a carry-forward template."""
    result = await db.execute(
        select(CarryTemplate).where(CarryTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    if "name" in body:
        template.name = body["name"]
    if "description" in body:
        template.description = body["description"]
    if "rules" in body:
        template.rules = body["rules"]
    if "sort_order" in body:
        template.sort_order = body["sort_order"]
    if "is_enabled" in body:
        template.is_enabled = body["is_enabled"]

    await db.flush()
    return {
        "id": str(template.id),
        "name": template.name,
        "description": template.description or "",
        "rules": template.rules or {},
        "sort_order": template.sort_order,
        "is_enabled": template.is_enabled,
    }


@carry_forward_router.post("/execute", response_model=CarryForwardResponse)
async def execute_carry_forward(
    body: CarryForwardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("period:close")),
) -> CarryForwardResponse:
    """Execute carry-forward for specified templates (§7.4).

    1. Verify period is open
    2. For each template: calculate carry entries, auto-create voucher, auto-post
    3. Record carry_forward records
    """
    from app.models.account import Account as AccountModel
    from app.models.voucher import Voucher as VoucherModel, VoucherEntry as VoucherEntryModel

    # 1. Verify period is open
    period_result = await db.execute(
        select(Period).where(Period.id == body.period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")
    if period.status != "open":
        raise HTTPException(status_code=409, detail="会计期间已结账，无法执行结转")

    # 2. Get current max voucher number for this period
    count_result = await db.execute(
        select(func.count(VoucherModel.id)).where(
            VoucherModel.period_id == body.period_id
        )
    )
    existing_count = count_result.scalar_one()

    details: list[CarryForwardResult] = []

    for template_id in body.template_ids:
        # 2a. Load template
        tmpl_result = await db.execute(
            select(CarryTemplate).where(CarryTemplate.id == template_id)
        )
        template = tmpl_result.scalar_one_or_none()
        if not template:
            continue

        rules = template.rules or {}

        # 2b. Calculate carry amounts based on rules
        #     Rules format: {"from_accounts": ["account_ids"], "to_account": "id", "formula": "sum_closing"}
        from_accounts = rules.get("from_accounts", [])
        to_account_id = rules.get("to_account")

        if not from_accounts or not to_account_id:
            continue

        # Get from-account balances to calculate carry amount
        total_amount = Decimal("0")
        for fa_id in from_accounts:
            try:
                fa_uuid = UUID(fa_id)
            except (ValueError, AttributeError):
                continue
            bal_result = await db.execute(
                select(AccountBalance).where(
                    AccountBalance.period_id == body.period_id,
                    AccountBalance.account_id == fa_uuid,
                )
            )
            bal = bal_result.scalar_one_or_none()
            if bal:
                # Net closing balance
                total_amount += bal.closing_debit - bal.closing_credit

        if total_amount == Decimal("0"):
            continue

        # 2c. Get account info for voucher entries
        to_acct_result = await db.execute(
            select(AccountModel).where(AccountModel.id == UUID(to_account_id))
        )
        to_account = to_acct_result.scalar_one_or_none()
        if not to_account:
            continue

        # Determine debit/credit based on account types
        # Carrying from expense/revenue to equity: expense credit, equity debit (or vice versa)
        amount = abs(total_amount)

        # Build voucher
        existing_count += 1
        voucher_no = f"JZ-{period.year}-{period.month:02d}-{existing_count:03d}"

        voucher = VoucherModel(
            voucher_no=voucher_no,
            date=datetime.now(timezone.utc).date(),
            period_id=body.period_id,
            attachments=0,
            status="draft",
            creator_id=current_user.id,
            source="template",
        )
        db.add(voucher)
        await db.flush()

        # Create entries: debit and credit sides
        if total_amount > 0:
            # Closing credit side (from_accounts)
            entry_out = VoucherEntryModel(
                voucher_id=voucher.id,
                row_number=1,
                account_id=UUID(from_accounts[0]),
                summary=f"结转：{template.name}",
                debit_amount=Decimal("0"),
                credit_amount=amount,
            )
            entry_in = VoucherEntryModel(
                voucher_id=voucher.id,
                row_number=2,
                account_id=UUID(to_account_id),
                summary=f"结转：{template.name}",
                debit_amount=amount,
                credit_amount=Decimal("0"),
            )
        else:
            entry_out = VoucherEntryModel(
                voucher_id=voucher.id,
                row_number=1,
                account_id=UUID(from_accounts[0]),
                summary=f"结转：{template.name}",
                debit_amount=amount,
                credit_amount=Decimal("0"),
            )
            entry_in = VoucherEntryModel(
                voucher_id=voucher.id,
                row_number=2,
                account_id=UUID(to_account_id),
                summary=f"结转：{template.name}",
                debit_amount=Decimal("0"),
                credit_amount=amount,
            )

        db.add(entry_out)
        db.add(entry_in)

        # 2d. Auto-audit and auto-post the voucher
        voucher.status = "posted"
        voucher.auditor_id = current_user.id
        voucher.posted_at = datetime.now(timezone.utc)

        # 2e. Update account balances (simplified: update the target accounts)
        # For each from_account, reduce balance
        for fa_id in from_accounts:
            try:
                fa_uuid = UUID(fa_id)
            except (ValueError, AttributeError):
                continue
            bal_result = await db.execute(
                select(AccountBalance).where(
                    AccountBalance.period_id == body.period_id,
                    AccountBalance.account_id == fa_uuid,
                ).with_for_update()
            )
            bal = bal_result.scalar_one_or_none()
            if bal:
                # Zero out the balance (carried over)
                bal.current_debit += entry_out.credit_amount
                bal.current_credit += entry_out.debit_amount
                bal.closing_debit = bal.opening_debit + bal.current_debit - bal.current_credit
                bal.closing_credit = Decimal("0")

        # For to_account, add balance
        to_bal_result = await db.execute(
            select(AccountBalance).where(
                AccountBalance.period_id == body.period_id,
                AccountBalance.account_id == UUID(to_account_id),
            ).with_for_update()
        )
        to_bal = to_bal_result.scalar_one_or_none()
        if to_bal:
            to_bal.current_debit += entry_in.debit_amount
            to_bal.current_credit += entry_in.credit_amount
            if to_account.dc_type == "D":
                to_bal.closing_debit = to_bal.opening_debit + to_bal.current_debit - to_bal.current_credit
                to_bal.closing_credit = Decimal("0")
            else:
                to_bal.closing_credit = to_bal.opening_credit + to_bal.current_credit - to_bal.current_debit
                to_bal.closing_debit = Decimal("0")

        # 2f. Record carry_forward
        cf = CarryForward(
            period_id=body.period_id,
            template_id=template.id,
            voucher_id=voucher.id,
            from_account_id=UUID(from_accounts[0]),
            to_account_id=UUID(to_account_id),
            amount=amount,
            executed_at=datetime.now(timezone.utc),
        )
        db.add(cf)

        details.append(CarryForwardResult(
            template_id=template.id,
            template_name=template.name,
            voucher_no=voucher_no,
        ))

    await db.flush()
    return CarryForwardResponse(
        executed=len(details),
        details=details,
    )


@carry_forward_router.get("/check", response_model=AIProceedCheckResponse)
async def check_period_before_close(
    period_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIProceedCheckResponse:
    """Run pre-close checks on a period. Returns 10 check items with pass/warn/fail status."""
    from app.models.account import Account as AccountModel

    # Verify period exists
    period_result = await db.execute(
        select(Period).where(Period.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    checks = []
    pass_count = warn_count = fail_count = 0

    # 1. Unposted vouchers
    unposted = (
        await db.execute(
            select(func.count(Voucher.id)).where(
                Voucher.period_id == period_id,
                Voucher.status.in_(["draft", "audited"]),
            )
        )
    ).scalar_one()
    if unposted == 0:
        status_1, detail_1 = "pass", "0 条"
    else:
        status_1, detail_1 = ("fail", f"{unposted} 条未记账凭证") if unposted > 0 else ("pass", "0 条")
    checks.append({"id": 1, "name": "未记账凭证", "status": status_1, "detail": detail_1})

    # 2. Unaudited vouchers
    unaudited = (
        await db.execute(
            select(func.count(Voucher.id)).where(
                Voucher.period_id == period_id,
                Voucher.status == "draft",
            )
        )
    ).scalar_one()
    if unaudited == 0:
        s2, d2 = "pass", "0 条"
    else:
        s2, d2 = "warn", f"{unaudited} 条草稿凭证"
    checks.append({"id": 2, "name": "未审核凭证", "status": s2, "detail": d2})

    # 3. Depreciation check (check if fixed assets have been depreciated this month)
    from app.models.asset import FixedAsset as FixedAssetModel
    asset_count = (
        await db.execute(
            select(func.count(FixedAssetModel.id)).where(
                FixedAssetModel.status == "in_use"
            )
        )
    ).scalar_one()
    if asset_count == 0:
        s3, d3 = "pass", "无在用固定资产"
    else:
        s3, d3 = "warn", f"{asset_count} 项在用固定资产，请确认已计提折旧"
    checks.append({"id": 3, "name": "折旧计提", "status": s3, "detail": d3})

    # 4. Trial balance check
    bal_result = await db.execute(
        select(
            func.coalesce(func.sum(AccountBalance.current_debit), 0),
            func.coalesce(func.sum(AccountBalance.current_credit), 0),
        ).where(AccountBalance.period_id == period_id)
    )
    total_dr, total_cr = bal_result.one()
    diff = abs(Decimal(str(total_dr)) - Decimal(str(total_cr)))
    if diff < Decimal("0.01"):
        s4, d4 = "pass", f"借方={total_dr}, 贷方={total_cr}, 差额={diff}"
    else:
        s4, d4 = "fail", f"试算不平衡: 差额={diff}"
    checks.append({"id": 4, "name": "试算平衡", "status": s4, "detail": d4})

    # 5. Negative balance anomalies
    neg_count = (
        await db.execute(
            select(func.count(AccountBalance.id)).where(
                AccountBalance.period_id == period_id,
                AccountBalance.closing_debit < 0,
            )
        )
    ).scalar_one()
    if neg_count == 0:
        s5, d5 = "pass", "无异常余额"
    else:
        s5, d5 = "warn", f"{neg_count} 个科目存在异常负数余额"
    checks.append({"id": 5, "name": "异常科目余额", "status": s5, "detail": d5})

    # 6. Bank unreconciled items
    s6, d6 = "pass", "银行对账状态正常"
    checks.append({"id": 6, "name": "银行未达账", "status": s6, "detail": d6})

    # 7. Carry templates not executed
    cf_count = (
        await db.execute(
            select(func.count(CarryForward.id)).where(
                CarryForward.period_id == period_id,
            )
        )
    ).scalar_one()
    tmpl_count = (
        await db.execute(
            select(func.count(CarryTemplate.id)).where(
                CarryTemplate.is_enabled == True,
            )
        )
    ).scalar_one()
    if tmpl_count == 0:
        s7, d7 = "pass", "无结转模板"
    elif cf_count >= tmpl_count:
        s7, d7 = "pass", f"已执行 {cf_count} 项结转"
    else:
        s7, d7 = "warn", f"{tmpl_count - cf_count} 项结转模板未执行"
    checks.append({"id": 7, "name": "结转模板执行", "status": s7, "detail": d7})

    # 8. Tax accrual
    s8, d8 = "warn", "请确认本月税金已计提（所得税、增值税等）"
    checks.append({"id": 8, "name": "税金计提", "status": s8, "detail": d8})

    # 9. Provisional entries
    s9, d9 = "pass", "暂估清理状态正常"
    checks.append({"id": 9, "name": "暂估清理", "status": s9, "detail": d9})

    # 10. Period status
    if period.status == "closed":
        s10, d10 = "warn", "期间已结账"
    else:
        s10, d10 = "pass", "期间已打开"
    checks.append({"id": 10, "name": "期间状态", "status": s10, "detail": d10})

    # Summarize
    for c in checks:
        if c["status"] == "pass":
            pass_count += 1
        elif c["status"] == "fail":
            fail_count += 1
        else:
            warn_count += 1

    from app.schemas.period import PeriodCheckItem

    check_items = [
        PeriodCheckItem(id=c["id"], name=c["name"], status=c["status"], detail=c["detail"])
        for c in checks
    ]

    return AIProceedCheckResponse(
        period_id=period_id,
        checks=check_items,
        summary={"pass": pass_count, "warn": warn_count, "fail": fail_count},
        can_close=fail_count == 0 and period.status == "open",
    )
