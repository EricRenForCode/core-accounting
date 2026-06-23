"""Voucher routes (§3.3) — 12 endpoints for full voucher lifecycle.

GET    /vouchers          — list with filtering
POST   /vouchers          — create voucher
GET    /vouchers/{id}     — detail with entries + auxiliaries
PUT    /vouchers/{id}     — update (draft only)
DELETE /vouchers/{id}     — soft delete (draft only)
POST   /vouchers/{id}/audit   — audit
POST   /vouchers/{id}/unaudit — unaudit
POST   /vouchers/{id}/post    — post to ledger
POST   /vouchers/{id}/reverse — reverse voucher
GET    /vouchers/{id}/print   — print data
POST   /vouchers/import       — batch import (Excel)
GET    /vouchers/export       — batch export (Excel)
"""

import math
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.models.voucher import Voucher, VoucherEntry, VoucherTemplate
from app.models.period import Period
from app.models.account import Account
from app.models.auxiliary import EntryAuxiliary
from app.schemas.common import PaginatedResponse
from app.schemas.voucher import (
    CreateVoucherRequest,
    ExportVoucherRequest,
    ImportVoucherRequest,
    UpdateVoucherRequest,
    VoucherEntryResponse,
    VoucherListParams,
    VoucherResponse,
)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────

def _invalidate_trial_balance_cache(period_id: str) -> None:
    """Best-effort cache invalidation for trial-balance reports.

    When Redis is available in production, this will delete keys matching
    the pattern `trial-balance:{period_id}*`. For now, it's a no-op since
    the data is always queried fresh from the account_balances snapshot.
    """
    try:
        pass  # Redis cache layer to be wired in later phase
    except Exception:
        pass  # Cache invalidation failure must not block the transaction


def _entry_to_response(entry: VoucherEntry) -> VoucherEntryResponse:
    """Convert a VoucherEntry ORM object to response schema."""
    account = entry.account
    return VoucherEntryResponse(
        id=entry.id,
        row_number=entry.row_number,
        account_id=entry.account_id,
        account={
            "id": str(account.id),
            "code": account.code,
            "name": account.name,
            "dc_type": account.dc_type,
        } if account else None,
        summary=entry.summary,
        debit_amount=entry.debit_amount,
        credit_amount=entry.credit_amount,
        quantity=entry.quantity,
        price=entry.price,
        auxiliaries=[
            {
                "id": str(a.id),
                "aux_type": a.aux_type,
                "department": {"id": str(a.department_id), "name": a.department.name} if a.department else None,
                "individual": {"id": str(a.individual_id), "name": a.individual.name} if a.individual else None,
                "counterparty": {"id": str(a.counterparty_id), "name": a.counterparty.name} if a.counterparty else None,
                "project": {"id": str(a.project_id), "name": a.project.name} if a.project else None,
            }
            for a in (entry.auxiliaries or [])
        ],
    )


def _voucher_to_response(v: Voucher) -> VoucherResponse:
    """Convert a Voucher ORM object to response schema."""
    return VoucherResponse(
        id=v.id,
        voucher_no=v.voucher_no,
        date=v.date,
        period_id=v.period_id,
        attachments=v.attachments,
        status=v.status,
        creator_id=v.creator_id,
        auditor_id=v.auditor_id,
        posted_at=v.posted_at,
        source=v.source,
        reversed_voucher_id=v.reversed_voucher_id,
        reversal_type=v.reversal_type,
        deleted_at=v.deleted_at,
        created_at=v.created_at,
        updated_at=v.updated_at,
        entries=[_entry_to_response(e) for e in (v.entries or [])],
    )


async def _generate_voucher_no(
    db: AsyncSession, period: Period
) -> str:
    """Generate next voucher number: {prefix}-{year}-{month:02d}-{serial:03d}."""
    # Get the prefix from system params, fallback to "JZ"
    from app.models.system_param import SystemParam
    result = await db.execute(
        select(SystemParam).where(SystemParam.key == "voucher_no_prefix")
    )
    param = result.scalar_one_or_none()
    prefix = param.value if param else "JZ"

    # Find max serial for this year-month
    pattern = f"{prefix}-{period.year}-{period.month:02d}-%"
    result = await db.execute(
        select(func.max(Voucher.voucher_no)).where(
            Voucher.voucher_no.like(pattern)
        )
    )
    max_no: Optional[str] = result.scalar_one_or_none()

    if max_no:
        try:
            serial = int(max_no.rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError):
            serial = 1
    else:
        serial = 1

    return f"{prefix}-{period.year}-{period.month:02d}-{serial:03d}"


@router.get("", response_model=PaginatedResponse[VoucherResponse])
async def list_vouchers(
    params: VoucherListParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[VoucherResponse]:
    """List vouchers with filtering, sorting, and pagination."""
    from sqlalchemy.orm import selectinload

    query = select(Voucher).where(Voucher.deleted_at.is_(None))
    count_q = select(func.count(Voucher.id)).where(Voucher.deleted_at.is_(None))

    if params.date_from:
        query = query.where(Voucher.date >= params.date_from)
        count_q = count_q.where(Voucher.date >= params.date_from)
    if params.date_to:
        query = query.where(Voucher.date <= params.date_to)
        count_q = count_q.where(Voucher.date <= params.date_to)
    if params.status:
        query = query.where(Voucher.status == params.status)
        count_q = count_q.where(Voucher.status == params.status)
    if params.period_id:
        query = query.where(Voucher.period_id == params.period_id)
        count_q = count_q.where(Voucher.period_id == params.period_id)
    if params.keyword:
        keyword_filter = Voucher.voucher_no.ilike(f"%{params.keyword}%")
        query = query.where(keyword_filter)
        count_q = count_q.where(keyword_filter)

    total_result = await db.execute(count_q)
    total: int = total_result.scalar_one()

    # Sorting
    sort_col = getattr(Voucher, params.sort, Voucher.date)
    if params.order == "desc":
        sort_col = sort_col.desc()
    query = query.order_by(sort_col)

    offset = (params.page - 1) * params.page_size
    query = (
        query
        .options(
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.account),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.department),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.individual),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.counterparty),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.project),
        )
        .offset(offset)
        .limit(params.page_size)
    )
    result = await db.execute(query)
    vouchers = result.unique().scalars().all()

    items = [_voucher_to_response(v) for v in vouchers]

    return PaginatedResponse(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        pages=math.ceil(total / params.page_size) if total > 0 else 1,
    )


@router.post("", response_model=VoucherResponse, status_code=201)
async def create_voucher(
    body: CreateVoucherRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> VoucherResponse:
    """Create a new voucher (draft status)."""
    from sqlalchemy.orm import selectinload

    # 1. Validate period is open
    period_result = await db.execute(
        select(Period).where(Period.id == body.period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")
    if period.status != "open":
        raise HTTPException(status_code=409, detail="会计期间已结账，无法创建凭证")

    # 2. Validate voucher date is within period
    if body.date.year != period.year or body.date.month != period.month:
        raise HTTPException(
            status_code=400,
            detail=f"凭证日期 {body.date} 不在期间 {period.year}-{period.month:02d} 范围内",
        )

    # 3. Validate all accounts exist and are enabled
    account_ids = {e.account_id for e in body.entries}
    acct_result = await db.execute(
        select(Account).where(Account.id.in_(account_ids))
    )
    accounts = {a.id: a for a in acct_result.scalars().all()}
    missing = account_ids - set(accounts.keys())
    if missing:
        raise HTTPException(status_code=404, detail=f"科目不存在: {missing}")
    for aid, acct in accounts.items():
        if not acct.is_enabled:
            raise HTTPException(status_code=400, detail=f"科目 {acct.code} {acct.name} 已禁用")

    # 4. Generate voucher_no
    voucher_no = await _generate_voucher_no(db, period)

    # 5. Create voucher
    voucher = Voucher(
        voucher_no=voucher_no,
        date=body.date,
        period_id=body.period_id,
        attachments=body.attachments,
        status="draft",
        creator_id=current_user.id,
        source="manual",
    )
    db.add(voucher)
    await db.flush()  # get voucher.id

    # 6. Create entries + auxiliaries
    for entry_data in body.entries:
        entry = VoucherEntry(
            voucher_id=voucher.id,
            row_number=entry_data.row_number,
            account_id=entry_data.account_id,
            summary=entry_data.summary,
            debit_amount=entry_data.debit_amount,
            credit_amount=entry_data.credit_amount,
            quantity=entry_data.quantity,
            price=entry_data.price,
        )
        db.add(entry)
        await db.flush()

        for aux_data in entry_data.auxiliaries:
            aux = EntryAuxiliary(
                entry_id=entry.id,
                aux_type=aux_data.aux_type,
                department_id=aux_data.department_id,
                individual_id=aux_data.individual_id,
                counterparty_id=aux_data.counterparty_id,
                project_id=aux_data.project_id,
            )
            db.add(aux)

    await db.flush()

    # 7. Reload with relationships
    result = await db.execute(
        select(Voucher)
        .options(
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.account),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.department),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.individual),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.counterparty),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.project),
        )
        .where(Voucher.id == voucher.id)
    )
    voucher = result.unique().scalar_one()

    return _voucher_to_response(voucher)


@router.get("/{voucher_id}", response_model=VoucherResponse)
async def get_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoucherResponse:
    """Get voucher detail with entries and auxiliary核算 references."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Voucher)
        .options(
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.account),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.department),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.individual),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.counterparty),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.project),
        )
        .where(Voucher.id == voucher_id, Voucher.deleted_at.is_(None))
    )
    voucher = result.unique().scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=404, detail="凭证不存在")

    return _voucher_to_response(voucher)


@router.put("/{voucher_id}", response_model=VoucherResponse)
async def update_voucher(
    voucher_id: UUID,
    body: UpdateVoucherRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> VoucherResponse:
    """Update voucher (only if status=draft).

    Permission: voucher:edit:own (own vouchers) or voucher:edit:any (all).
    §7.1 constraint: posted vouchers are immutable — reject edit attempts.
    """
    from sqlalchemy.orm import selectinload

    # 1. Load voucher
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id, Voucher.deleted_at.is_(None))
    )
    voucher = result.scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=404, detail="凭证不存在")

    # 2. Assert draft status (posted/audited vouchers are immutable)
    if voucher.status != "draft":
        raise HTTPException(status_code=409, detail=f"凭证状态为 {voucher.status}，不可编辑")

    # 3. Permission check: creator can edit own, or need voucher:edit:any
    if voucher.creator_id != current_user.id:
        # Editing someone else's voucher — require voucher:edit:any
        from app.core.security import require_permission
        # If we got here with voucher:create permission, check edit:any separately
        # For now, reject non-creator edits (voucher:edit:any check done via dependency)
        raise HTTPException(status_code=403, detail="只能编辑自己创建的凭证")

    # 4. Update fields
    if body.date:
        voucher.date = body.date
    if body.attachments is not None:
        voucher.attachments = body.attachments

    # 5. If entries provided: delete old, recreate from body
    if body.entries:
        # Delete old entries
        for old_entry in list(voucher.entries):
            await db.delete(old_entry)
        await db.flush()

        # Create new entries
        for entry_data in body.entries:
            entry = VoucherEntry(
                voucher_id=voucher.id,
                row_number=entry_data.row_number,
                account_id=entry_data.account_id,
                summary=entry_data.summary,
                debit_amount=entry_data.debit_amount,
                credit_amount=entry_data.credit_amount,
                quantity=entry_data.quantity,
                price=entry_data.price,
            )
            db.add(entry)
            await db.flush()

            for aux_data in entry_data.auxiliaries:
                aux = EntryAuxiliary(
                    entry_id=entry.id,
                    aux_type=aux_data.aux_type,
                    department_id=aux_data.department_id,
                    individual_id=aux_data.individual_id,
                    counterparty_id=aux_data.counterparty_id,
                    project_id=aux_data.project_id,
                )
                db.add(aux)

    await db.flush()

    # 6. Reload with relationships
    result = await db.execute(
        select(Voucher)
        .options(
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.account),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.department),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.individual),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.counterparty),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.project),
        )
        .where(Voucher.id == voucher_id)
    )
    voucher = result.unique().scalar_one()

    return _voucher_to_response(voucher)


@router.delete("/{voucher_id}")
async def delete_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:delete:draft")),
) -> dict:
    """Soft-delete a draft voucher (sets deleted_at).

    Permission: voucher:delete:draft
    §7.1 constraint: posted vouchers are immutable — reject delete attempts.
    """
    from datetime import datetime as dt, timezone

    # 1. Load voucher
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id, Voucher.deleted_at.is_(None))
    )
    voucher = result.scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=404, detail="凭证不存在")

    # 2. Assert draft status only
    if voucher.status != "draft":
        raise HTTPException(status_code=409, detail=f"凭证状态为 {voucher.status}，不可删除")

    # 3. Soft delete
    voucher.deleted_at = dt.now(timezone.utc)

    return {"message": "凭证已删除"}


@router.post("/{voucher_id}/audit", response_model=VoucherResponse)
async def audit_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:audit")),
) -> VoucherResponse:
    """Audit a draft voucher (status: draft → audited).

    Logic (§7.1 pre-condition):
    1. Verify voucher exists and status=draft
    2. Verify voucher is balanced (total debit == total credit)
    3. Verify period is open
    4. Set status='audited', auditor_id=current_user.id
    5. Return voucher
    """
    from sqlalchemy.orm import selectinload

    # 1. Load voucher with entries
    result = await db.execute(
        select(Voucher)
        .options(
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.account),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.department),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.individual),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.counterparty),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.project),
        )
        .where(Voucher.id == voucher_id, Voucher.deleted_at.is_(None))
    )
    voucher = result.unique().scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=404, detail="凭证不存在")

    # 2. Assert status is draft
    if voucher.status != "draft":
        raise HTTPException(status_code=409, detail="只能审核草稿状态的凭证")

    # 3. CRITICAL: Creator cannot audit their own voucher
    if voucher.creator_id == current_user.id:
        raise HTTPException(
            status_code=403, detail="制单人不可审核自己的凭证"
        )

    # 4. Assert period is open
    period_result = await db.execute(
        select(Period).where(Period.id == voucher.period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period or period.status != "open":
        raise HTTPException(status_code=409, detail="会计期间已结账，无法审核凭证")

    # 5. Verify balance: sum(debit) == sum(credit)
    total_debit = sum(
        (e.debit_amount for e in voucher.entries), Decimal("0")
    )
    total_credit = sum(
        (e.credit_amount for e in voucher.entries), Decimal("0")
    )
    if total_debit != total_credit:
        raise HTTPException(
            status_code=409,
            detail=f"凭证借贷不平衡：借方合计 {total_debit}，贷方合计 {total_credit}",
        )

    # 6. Set status and auditor
    voucher.status = "audited"
    voucher.auditor_id = current_user.id
    await db.commit()
    await db.refresh(voucher)

    return _voucher_to_response(voucher)


@router.post("/{voucher_id}/unaudit", response_model=VoucherResponse)
async def unaudit_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:unaudit")),
) -> VoucherResponse:
    """Reverse audit: audited → draft.

    Only allowed if voucher has not been posted.
    """
    from sqlalchemy.orm import selectinload

    # 1. Load voucher with entries
    result = await db.execute(
        select(Voucher)
        .options(
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.account),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.department),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.individual),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.counterparty),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.project),
        )
        .where(Voucher.id == voucher_id, Voucher.deleted_at.is_(None))
    )
    voucher = result.unique().scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=404, detail="凭证不存在")

    # 2. Assert status is audited
    if voucher.status != "audited":
        raise HTTPException(status_code=409, detail="只能反审核已审核状态的凭证")

    # 3. Assert voucher has not been posted
    if voucher.posted_at is not None:
        raise HTTPException(status_code=409, detail="已记账的凭证不能反审核")

    # 4. Revert status and clear auditor
    voucher.status = "draft"
    voucher.auditor_id = None
    await db.commit()
    await db.refresh(voucher)

    return _voucher_to_response(voucher)


@router.post("/{voucher_id}/post", response_model=VoucherResponse)
async def post_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:post")),
) -> VoucherResponse:
    """Post a voucher to the ledger (status: audited → posted).

    §7.1 — Core accounting operation executed within the request transaction:
    1. Load voucher with entries + accounts (needed for dc_type)
    2. Verify voucher.status == 'audited'
    3. Lock period row (SELECT FOR UPDATE) to prevent concurrent close
    4. Verify period is open
    5. Set voucher.status = 'posted', voucher.posted_at = NOW()
    6. Aggregate entries by account_id (reduce row-lock contention)
    7. For each account: upsert AccountBalance with SELECT FOR UPDATE
       - Increment current_debit/current_credit
       - Recalculate closing_debit/closing_credit based on account.dc_type
    8. Audit log written automatically by after_flush listener
    9. Invalidate trial-balance cache for this period (best-effort)
    """
    from datetime import datetime as dt, timezone
    from sqlalchemy.orm import selectinload
    from app.models.period import AccountBalance

    # 1. Load voucher with entries + accounts
    result = await db.execute(
        select(Voucher)
        .options(
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.account),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.department),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.individual),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.counterparty),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.project),
        )
        .where(Voucher.id == voucher_id, Voucher.deleted_at.is_(None))
    )
    voucher = result.unique().scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=404, detail="凭证不存在")

    # 2. Assert status is audited
    if voucher.status != "audited":
        raise HTTPException(status_code=409, detail="只能记账已审核状态的凭证")

    # 3. Lock period row to prevent concurrent close
    period_result = await db.execute(
        select(Period)
        .where(Period.id == voucher.period_id)
        .with_for_update()
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    # 4. Verify period is open
    if period.status != "open":
        raise HTTPException(status_code=409, detail="会计期间已结账，无法记账")

    # 5. Set voucher status and posted_at
    now = dt.now(timezone.utc)
    voucher.status = "posted"
    voucher.posted_at = now

    # 6. Aggregate entries by account_id (reduce row-lock count)
    account_totals: dict[uuid.UUID, dict] = {}
    for entry in voucher.entries:
        acct = entry.account
        if not acct:
            raise HTTPException(
                status_code=500, detail=f"分录科目不存在: entry {entry.id}"
            )
        key = entry.account_id
        if key not in account_totals:
            account_totals[key] = {
                "debit": Decimal("0"),
                "credit": Decimal("0"),
                "dc_type": acct.dc_type,
            }
        account_totals[key]["debit"] += entry.debit_amount
        account_totals[key]["credit"] += entry.credit_amount

    # 7. For each affected account: upsert AccountBalance with row lock
    for account_id, totals in account_totals.items():
        balance_result = await db.execute(
            select(AccountBalance)
            .where(
                AccountBalance.period_id == period.id,
                AccountBalance.account_id == account_id,
            )
            .with_for_update()
        )
        balance = balance_result.scalar_one_or_none()

        if not balance:
            balance = AccountBalance(
                period_id=period.id,
                account_id=account_id,
            )
            db.add(balance)
            await db.flush()  # get defaults applied before increment

        # Increment current period amounts
        balance.current_debit += totals["debit"]
        balance.current_credit += totals["credit"]

        # Recalculate closing balance based on account direction (dc_type)
        if totals["dc_type"] == "D":
            balance.closing_debit = (
                balance.opening_debit
                + balance.current_debit
                - balance.current_credit
            )
            balance.closing_credit = Decimal("0")
        else:  # dc_type == "C"
            balance.closing_credit = (
                balance.opening_credit
                + balance.current_credit
                - balance.current_debit
            )
            balance.closing_debit = Decimal("0")

    # 8. Audit log — written automatically by SQLAlchemy after_flush listener
    #    (tracks Voucher.status UPDATE and AccountBalance INSERT/UPDATE)

    # 9. Invalidate trial-balance cache (best-effort — Redis may not be configured)
    _invalidate_trial_balance_cache(str(period.id))

    await db.flush()
    await db.refresh(voucher)

    return _voucher_to_response(voucher)


@router.post("/{voucher_id}/reverse", response_model=VoucherResponse, status_code=201)
async def reverse_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:reverse")),
) -> VoucherResponse:
    """Reverse a posted voucher — creates a new voucher with debit/credit swapped.

    §3.3 — 红字冲销：
    1. Verify original voucher.status == 'posted' and not already reversed
    2. Create reversal voucher with same entries but debit↔credit swapped
    3. Set source='reversal', reversed_voucher_id=original.id, reversal_type='full'
    4. Original voucher.status = 'reversed'
    5. Return the reversal voucher (draft — manual audit + post required)
    """
    from datetime import date as dt_date
    from sqlalchemy.orm import selectinload

    # 1. Load original voucher with entries
    result = await db.execute(
        select(Voucher)
        .options(
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries),
        )
        .where(Voucher.id == voucher_id, Voucher.deleted_at.is_(None))
    )
    original = result.unique().scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="凭证不存在")

    # 2. Assert status is posted and not already reversed
    if original.status != "posted":
        raise HTTPException(status_code=409, detail="只能冲销已记账的凭证")
    if original.status == "reversed":
        raise HTTPException(status_code=409, detail="该凭证已被冲销")

    # 3. Generate voucher_no for reversal
    period = original.period
    reversal_no = await _generate_voucher_no(db, period)

    # 4. Create reversal voucher (draft — swaps debit↔credit)
    reversal = Voucher(
        voucher_no=reversal_no,
        date=dt_date.today(),
        period_id=original.period_id,
        attachments=original.attachments,
        status="draft",
        creator_id=current_user.id,
        source="reversal",
        reversed_voucher_id=original.id,
        reversal_type="full",
    )
    db.add(reversal)
    await db.flush()

    # 5. Copy entries with debit↔credit swapped
    for orig_entry in original.entries:
        reversal_entry = VoucherEntry(
            voucher_id=reversal.id,
            row_number=orig_entry.row_number,
            account_id=orig_entry.account_id,
            summary=f"[冲销] {orig_entry.summary}",
            debit_amount=orig_entry.credit_amount,   # swap
            credit_amount=orig_entry.debit_amount,   # swap
            quantity=orig_entry.quantity,
            price=orig_entry.price,
        )
        db.add(reversal_entry)
        await db.flush()

        # Copy auxiliaries
        for orig_aux in (orig_entry.auxiliaries or []):
            aux = EntryAuxiliary(
                entry_id=reversal_entry.id,
                aux_type=orig_aux.aux_type,
                department_id=orig_aux.department_id,
                individual_id=orig_aux.individual_id,
                counterparty_id=orig_aux.counterparty_id,
                project_id=orig_aux.project_id,
            )
            db.add(aux)

    # 6. Mark original as reversed
    original.status = "reversed"

    await db.flush()

    # 7. Reload reversal with all relationships
    result = await db.execute(
        select(Voucher)
        .options(
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.account),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.department),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.individual),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.counterparty),
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.auxiliaries)
            .selectinload(EntryAuxiliary.project),
        )
        .where(Voucher.id == reversal.id)
    )
    reversal = result.unique().scalar_one()

    return _voucher_to_response(reversal)


@router.get("/{voucher_id}/print")
async def print_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get print-formatted voucher data (for PDF/print rendering)."""
    raise NotImplementedError(
        "print_voucher:\n"
        "1. Get voucher with entries, accounts, auxiliaries\n"
        "2. Format for print: company header, voucher no, date, entries table, signatures\n"
        "3. Return print-ready data structure"
    )


@router.post("/import")
async def import_vouchers(
    file: UploadFile,
    period_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> dict:
    """Import vouchers from Excel file.

    Expected Excel columns:
      voucher_no | date | account_code | summary | debit_amount | credit_amount

    Rows with the same voucher_no are grouped into a single voucher.
    """
    import io
    from datetime import date as dt_date
    from openpyxl import load_workbook
    from decimal import Decimal, InvalidOperation

    # 1. Read Excel
    content = await file.read()
    try:
        wb = load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.active
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无法解析 Excel 文件: {str(e)}")

    # 2. Parse header row
    rows = list(ws.iter_rows(min_row=1, values_only=True))
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="Excel 文件至少需要表头和数据行")

    headers = [str(h).lower().strip() if h else '' for h in rows[0]]
    expected = ['voucher_no', 'date', 'account_code', 'summary', 'debit_amount', 'credit_amount']
    col_map = {}
    for exp in expected:
        if exp in headers:
            col_map[exp] = headers.index(exp)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"缺少必需列: {exp}。期望列: {', '.join(expected)}",
            )

    # 3. Pre-load accounts by code
    acct_result = await db.execute(
        select(Account).where(Account.is_enabled == True)
    )
    accounts_by_code: dict[str, Account] = {
        a.code: a for a in acct_result.scalars().all()
    }

    # 4. Parse rows, group by voucher_no
    errors: list[dict] = []
    voucher_groups: dict[str, list[dict]] = {}

    for row_idx, row in enumerate(rows[1:], start=2):
        try:
            voucher_no = str(row[col_map['voucher_no']] or '').strip()
            if not voucher_no:
                errors.append({"row": row_idx, "error": "凭证号为空"})
                continue

            date_str = str(row[col_map['date']] or '').strip()
            try:
                from datetime import datetime
                if '-' in date_str:
                    voucher_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    voucher_date = datetime.strptime(date_str, '%Y%m%d').date()
            except ValueError:
                errors.append({"row": row_idx, "error": f"日期格式错误: {date_str}"})
                continue

            account_code = str(row[col_map['account_code']] or '').strip()
            if account_code not in accounts_by_code:
                errors.append({"row": row_idx, "error": f"科目代码不存在: {account_code}"})
                continue

            summary = str(row[col_map['summary']] or '').strip()
            if not summary:
                errors.append({"row": row_idx, "error": "摘要为空"})
                continue

            try:
                debit = Decimal(str(row[col_map['debit_amount']] or 0))
                credit = Decimal(str(row[col_map['credit_amount']] or 0))
            except (InvalidOperation, ValueError):
                errors.append({"row": row_idx, "error": "金额格式错误"})
                continue

            if debit == 0 and credit == 0:
                errors.append({"row": row_idx, "error": "借贷金额均为0"})
                continue

            if debit > 0 and credit > 0:
                errors.append({"row": row_idx, "error": "借贷金额互斥（不能同时大于0）"})
                continue

            entry = {
                "row": row_idx,
                "voucher_no": voucher_no,
                "date": voucher_date,
                "account_code": account_code,
                "summary": summary,
                "debit": debit,
                "credit": credit,
            }

            if voucher_no not in voucher_groups:
                voucher_groups[voucher_no] = []
            voucher_groups[voucher_no].append(entry)

        except Exception as e:
            errors.append({"row": row_idx, "error": str(e)})

    # 5. Validate and create vouchers
    imported = 0
    for voucher_no, entries_data in voucher_groups.items():
        # Check: all entries have same date
        dates = {e['date'] for e in entries_data}
        if len(dates) > 1:
            errors.append({"voucher_no": voucher_no, "error": "同一凭证号下有不同日期"})
            continue
        voucher_date = dates.pop()

        # Validate balance
        total_debit = sum(e['debit'] for e in entries_data)
        total_credit = sum(e['credit'] for e in entries_data)
        if abs(total_debit - total_credit) > Decimal('0.01'):
            errors.append({
                "voucher_no": voucher_no,
                "error": f"借贷不平衡：借{total_debit} 贷{total_credit}",
            })
            continue

        # Create voucher
        try:
            period_result = await db.execute(
                select(Period).where(Period.id == period_id)
            )
            period = period_result.scalar_one_or_none()
            if not period or period.status != "open":
                errors.append({"voucher_no": voucher_no, "error": "会计期间未开启"})
                continue

            voucher = Voucher(
                voucher_no=voucher_no,
                date=voucher_date,
                period_id=period_id,
                attachments=0,
                status="draft",
                creator_id=current_user.id,
                source="import",
            )
            db.add(voucher)
            await db.flush()

            for i, ed in enumerate(entries_data, start=1):
                account = accounts_by_code[ed['account_code']]
                entry = VoucherEntry(
                    voucher_id=voucher.id,
                    row_number=i,
                    account_id=account.id,
                    summary=ed['summary'],
                    debit_amount=ed['debit'],
                    credit_amount=ed['credit'],
                )
                db.add(entry)

            await db.flush()
            imported += 1

        except Exception as e:
            errors.append({"voucher_no": voucher_no, "error": f"创建失败: {str(e)}"})

    return {
        "imported": imported,
        "skipped": len(voucher_groups) - imported,
        "errors": errors,
    }


@router.get("/export")
async def export_vouchers(
    params: ExportVoucherRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export vouchers to Excel (same filter params as list).

    Returns an Excel file with one row per voucher entry line.
    """
    import io
    from datetime import datetime as dt
    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from sqlalchemy.orm import selectinload

    # 1. Query vouchers with entries (no pagination)
    query = select(Voucher).where(Voucher.deleted_at.is_(None))

    if params.date_from:
        query = query.where(Voucher.date >= params.date_from)
    if params.date_to:
        query = query.where(Voucher.date <= params.date_to)
    if params.status:
        query = query.where(Voucher.status == params.status)
    if params.period_id:
        query = query.where(Voucher.period_id == params.period_id)
    if params.keyword:
        keyword_filter = Voucher.voucher_no.ilike(f"%{params.keyword}%")
        query = query.where(keyword_filter)

    query = (
        query
        .options(
            selectinload(Voucher.entries)
            .selectinload(VoucherEntry.account),
        )
        .order_by(Voucher.date.desc(), Voucher.voucher_no)
    )

    result = await db.execute(query)
    vouchers = result.unique().scalars().all()

    # 2. Build Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "凭证导出"

    # Header style
    header_font = Font(bold=True, size=11)
    header_fill = PatternFill(start_color="F0F0F0", end_color="F0F0F0", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin'),
    )

    # Headers
    headers = ['凭证号', '日期', '状态', '科目编码', '科目名称', '摘要', '借方金额', '贷方金额']
    for col, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='center')

    # Data rows
    row_num = 2
    status_labels = {
        'draft': '草稿', 'audited': '已审核', 'posted': '已记账', 'reversed': '已冲销',
    }

    for voucher in vouchers:
        status_label = status_labels.get(voucher.status, voucher.status)
        for entry in (voucher.entries or []):
            account = entry.account
            ws.cell(row=row_num, column=1, value=voucher.voucher_no).border = thin_border
            ws.cell(row=row_num, column=2, value=voucher.date.isoformat()).border = thin_border
            ws.cell(row=row_num, column=3, value=status_label).border = thin_border
            ws.cell(row=row_num, column=4, value=account.code if account else '').border = thin_border
            ws.cell(row=row_num, column=5, value=account.name if account else '').border = thin_border
            ws.cell(row=row_num, column=6, value=entry.summary).border = thin_border
            ws.cell(row=row_num, column=7, value=float(entry.debit_amount)).border = thin_border
            ws.cell(row=row_num, column=8, value=float(entry.credit_amount)).border = thin_border

            # Number format for amounts
            ws.cell(row=row_num, column=7).number_format = '#,##0.00'
            ws.cell(row=row_num, column=8).number_format = '#,##0.00'
            row_num += 1

    # Column widths
    col_widths = [22, 14, 10, 16, 22, 30, 16, 16]
    for col, w in enumerate(col_widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = w

    # 3. Write to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"vouchers-export-{dt.now().strftime('%Y%m%d-%H%M%S')}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
