"""Dashboard summary route (§3.14).

GET /dashboard/summary — period overview with voucher counts, trial balance status, recent activity.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/summary")
async def dashboard_summary(
    period_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Dashboard summary for the given period.

    If period_id not provided, uses the current open period.

    Returns:
    - period info
    - voucher counts by status (draft, audited, posted, total)
    - trial balance status (is_balanced, total_debit, total_credit)
    - recent activity (last 10 audit_log entries)
    """
    raise NotImplementedError(
        "dashboard_summary:\n"
        "1. If period_id is None: SELECT period WHERE status='open' (latest)\n"
        "2. Count vouchers by status:\n"
        "     SELECT status, COUNT(*) FROM vouchers WHERE period_id=... AND deleted_at IS NULL GROUP BY status\n"
        "3. Trial balance:\n"
        "     SELECT SUM(current_debit), SUM(current_credit) FROM account_balances WHERE period_id=...\n"
        "     is_balanced = total_debit == total_credit\n"
        "4. Recent activity:\n"
        "     SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 10\n"
        "5. Return:\n"
        "   {\n"
        "     period: {id, year, month},\n"
        "     voucher_counts: {draft, audited, posted, total},\n"
        "     trial_balance: {total_debit, total_credit, is_balanced},\n"
        "     recent_activity: [{action, resource_type, resource_id, created_at}]\n"
        "   }"
    )
