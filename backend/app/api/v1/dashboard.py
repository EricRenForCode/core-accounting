"""Dashboard summary route (§3.14).

GET /dashboard/summary — period overview with voucher counts, trial balance status, recent activity.
"""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit import AuditLog
from app.models.period import AccountBalance, Period
from app.models.user import User
from app.models.voucher import Voucher

router = APIRouter()


@router.get("/summary")
async def dashboard_summary(
    period_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Dashboard summary for the given period.

    If period_id not provided, uses the current open period (latest by year/month).

    Returns:
    - period info {id, year, month, status}
    - voucher counts by status {draft, audited, posted, reversed, total}
    - trial balance status {total_debit, total_credit, is_balanced}
    - recent activity (last 10 audit_log entries with operator name)
    """
    # 1. Resolve target period
    if period_id is not None:
        period = (
            await db.execute(select(Period).where(Period.id == period_id))
        ).scalar_one_or_none()
    else:
        period = (
            await db.execute(
                select(Period)
                .where(Period.status == "open")
                .order_by(Period.year.desc(), Period.month.desc())
            )
        ).scalars().first()
        # Fall back to the latest period of any status
        if period is None:
            period = (
                await db.execute(
                    select(Period).order_by(
                        Period.year.desc(), Period.month.desc()
                    )
                )
            ).scalars().first()

    period_info = (
        {
            "id": str(period.id),
            "year": period.year,
            "month": period.month,
            "status": period.status,
        }
        if period
        else None
    )

    # 2. Voucher counts by status (current period)
    voucher_counts = {
        "draft": 0,
        "audited": 0,
        "posted": 0,
        "reversed": 0,
        "total": 0,
    }
    if period:
        rows = await db.execute(
            select(Voucher.status, func.count())
            .where(
                Voucher.period_id == period.id,
                Voucher.deleted_at.is_(None),
            )
            .group_by(Voucher.status)
        )
        for status, count in rows:
            voucher_counts[status] = count
            voucher_counts["total"] += count

    # 3. Trial balance (current period)
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    if period:
        tb = (
            await db.execute(
                select(
                    func.coalesce(func.sum(AccountBalance.current_debit), 0),
                    func.coalesce(func.sum(AccountBalance.current_credit), 0),
                ).where(AccountBalance.period_id == period.id)
            )
        ).one()
        total_debit = Decimal(str(tb[0]))
        total_credit = Decimal(str(tb[1]))

    trial_balance = {
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": abs(total_debit - total_credit) < Decimal("0.01"),
    }

    # 4. Recent activity — last 10 audit log entries with operator name
    activity_rows = await db.execute(
        select(AuditLog, User.display_name, User.username)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    )
    recent_activity = [
        {
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": str(log.resource_id) if log.resource_id else None,
            "user": display_name or username,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log, display_name, username in activity_rows
    ]

    return {
        "period": period_info,
        "voucher_counts": voucher_counts,
        "trial_balance": trial_balance,
        "recent_activity": recent_activity,
    }
