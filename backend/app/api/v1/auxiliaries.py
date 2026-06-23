"""Auxiliary核算 routes (§3.9).

GET    /auxiliaries/{type}          — archive list (departments/individuals/counterparties/projects)
POST   /auxiliaries/{type}          — create archive entry
PUT    /auxiliaries/{type}/{id}     — update
DELETE /auxiliaries/{type}/{id}     — delete (check references)
GET    /auxiliaries/{type}/{id}/ledger — auxiliary核算明细账
GET    /auxiliaries/{type}/{id}/aging   — 账龄分析
"""

import uuid as _uuid
from datetime import date as date_type, datetime
from typing import Type

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.models.auxiliary import (
    Counterparty,
    Department,
    EntryAuxiliary,
    Individual,
    Project,
)
from app.schemas.common import PaginatedResponse
from app.schemas.period import (
    AgingBucket,
    AgingResponse,
    AuxArchiveCreate,
    AuxArchiveResponse,
    AuxArchiveUpdate,
    AuxLedgerResponse,
    AuxLedgerRow,
)

router = APIRouter()

VALID_AUX_TYPES = {"departments", "individuals", "counterparties", "projects"}

# Map aux_type string → SQLAlchemy model
AUX_MODEL_MAP: dict[str, Type] = {
    "departments": Department,
    "individuals": Individual,
    "counterparties": Counterparty,
    "projects": Project,
}

# Column name in EntryAuxiliary for each aux_type
AUX_FK_MAP: dict[str, str] = {
    "departments": "department_id",
    "individuals": "individual_id",
    "counterparties": "counterparty_id",
    "projects": "project_id",
}


@router.get("/{aux_type}", response_model=PaginatedResponse[AuxArchiveResponse])
async def list_auxiliaries(
    aux_type: str = Path(..., description="departments/individuals/counterparties/projects"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_enabled: bool = Query(None),
    search: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("aux:manage")),
) -> PaginatedResponse[AuxArchiveResponse]:
    """List auxiliary archive entries for the given type."""
    if aux_type not in VALID_AUX_TYPES:
        raise HTTPException(400, f"Invalid aux_type: {aux_type}")

    model = AUX_MODEL_MAP[aux_type]

    # Base query
    q = select(model)
    count_q = select(func.count(model.id))

    # Filters
    if is_enabled is not None:
        q = q.where(model.is_enabled == is_enabled)
        count_q = count_q.where(model.is_enabled == is_enabled)

    if search:
        pattern = f"%{search}%"
        q = q.where(
            (model.name.ilike(pattern)) | (model.code.ilike(pattern))
        )
        count_q = count_q.where(
            (model.name.ilike(pattern)) | (model.code.ilike(pattern))
        )

    # Count
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Paginate + sort
    offset = (page - 1) * page_size
    q = q.order_by(model.code).offset(offset).limit(page_size)
    result = await db.execute(q)
    items = list(result.scalars().all())

    return PaginatedResponse(
        items=[AuxArchiveResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=((total + page_size - 1) // page_size) if total > 0 else 0,
    )


@router.post("/{aux_type}", response_model=AuxArchiveResponse, status_code=201)
async def create_auxiliary(
    aux_type: str,
    body: AuxArchiveCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("aux:manage")),
) -> AuxArchiveResponse:
    """Create an auxiliary archive entry."""
    if aux_type not in VALID_AUX_TYPES:
        raise HTTPException(400, f"Invalid aux_type: {aux_type}")

    model = AUX_MODEL_MAP[aux_type]

    # Check code uniqueness
    existing = await db.execute(
        select(model).where(model.code == body.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"编码 {body.code} 已存在")

    entity = model(
        code=body.code,
        name=body.name,
        is_enabled=body.is_enabled,
    )
    db.add(entity)
    await db.commit()
    await db.refresh(entity)

    return AuxArchiveResponse.model_validate(entity)


@router.put("/{aux_type}/{aux_id}", response_model=AuxArchiveResponse)
async def update_auxiliary(
    aux_type: str,
    aux_id: _uuid.UUID,
    body: AuxArchiveUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("aux:manage")),
) -> AuxArchiveResponse:
    """Update an auxiliary archive entry."""
    if aux_type not in VALID_AUX_TYPES:
        raise HTTPException(400, f"Invalid aux_type: {aux_type}")

    model = AUX_MODEL_MAP[aux_type]

    entity_result = await db.execute(
        select(model).where(model.id == aux_id)
    )
    entity = entity_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(404, f"{aux_type} {aux_id} 不存在")

    # Check code uniqueness if code changed
    if body.code and body.code != entity.code:
        dup = await db.execute(
            select(model).where(model.code == body.code, model.id != aux_id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(409, f"编码 {body.code} 已存在")

    # Patch fields
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entity, key, value)

    await db.commit()
    await db.refresh(entity)

    return AuxArchiveResponse.model_validate(entity)


@router.delete("/{aux_type}/{aux_id}")
async def delete_auxiliary(
    aux_type: str,
    aux_id: _uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("aux:manage")),
) -> dict:
    """Delete an auxiliary archive entry (only if no voucher entries reference it)."""
    if aux_type not in VALID_AUX_TYPES:
        raise HTTPException(400, f"Invalid aux_type: {aux_type}")

    model = AUX_MODEL_MAP[aux_type]
    fk_column = AUX_FK_MAP[aux_type]

    entity_result = await db.execute(
        select(model).where(model.id == aux_id)
    )
    entity = entity_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(404, f"{aux_type} {aux_id} 不存在")

    # Check if referenced in entry_auxiliaries
    ref_check = await db.execute(
        select(func.count(EntryAuxiliary.id)).where(
            getattr(EntryAuxiliary, fk_column) == aux_id
        )
    )
    ref_count = ref_check.scalar() or 0
    if ref_count > 0:
        raise HTTPException(
            409,
            f"该档案被 {ref_count} 条凭证分录引用，无法删除",
        )

    await db.delete(entity)
    await db.commit()

    return {"message": "ok"}


@router.get("/{aux_type}/{aux_id}/ledger", response_model=AuxLedgerResponse)
async def aux_ledger(
    aux_type: str,
    aux_id: _uuid.UUID,
    period_id: _uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ledger:read")),
) -> AuxLedgerResponse:
    """辅助核算明细账 — filtered ledger for a specific auxiliary entity."""
    if aux_type not in VALID_AUX_TYPES:
        raise HTTPException(400, f"Invalid aux_type: {aux_type}")

    from decimal import Decimal as D

    from app.models.voucher import Voucher, VoucherEntry
    from app.models.account import Account as AccountModel

    model = AUX_MODEL_MAP[aux_type]
    fk_column = AUX_FK_MAP[aux_type]

    # 1. Get entity
    entity_result = await db.execute(
        select(model).where(model.id == aux_id)
    )
    entity = entity_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(404, detail=f"{aux_type} {aux_id} 不存在")

    # 2. Query entries linked to this auxiliary entity within the period
    result = await db.execute(
        select(VoucherEntry, Voucher, AccountModel)
        .join(EntryAuxiliary, EntryAuxiliary.entry_id == VoucherEntry.id)
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .join(AccountModel, VoucherEntry.account_id == AccountModel.id)
        .where(
            getattr(EntryAuxiliary, fk_column) == aux_id,
            Voucher.period_id == period_id,
            Voucher.status == "posted",
            Voucher.deleted_at.is_(None),
        )
        .order_by(Voucher.date, Voucher.voucher_no, VoucherEntry.row_number)
    )

    rows: list[AuxLedgerRow] = []
    total_debit = D("0")
    total_credit = D("0")
    balance = D("0")

    for entry, voucher, account in result:
        total_debit += entry.debit_amount
        total_credit += entry.credit_amount
        balance = balance + entry.debit_amount - entry.credit_amount

        rows.append(AuxLedgerRow(
            date=voucher.date,
            voucher_no=voucher.voucher_no,
            summary=entry.summary,
            account_code=account.code,
            account_name=account.name,
            debit=entry.debit_amount,
            credit=entry.credit_amount,
            balance=balance,
        ))

    return AuxLedgerResponse(
        aux_type=aux_type,
        entity={"id": str(entity.id), "code": entity.code, "name": entity.name},
        period_id=period_id,
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
        closing_balance=balance,
    )


@router.get("/{aux_type}/{aux_id}/aging", response_model=AgingResponse)
async def aux_aging(
    aux_type: str,
    aux_id: _uuid.UUID,
    as_of_date: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:read")),
) -> AgingResponse:
    """账龄分析 — aging analysis for the auxiliary entity (typically counterparties)."""
    if aux_type not in VALID_AUX_TYPES:
        raise HTTPException(400, f"Invalid aux_type: {aux_type}")

    from datetime import date
    from decimal import Decimal as D

    from app.models.voucher import Voucher, VoucherEntry

    model = AUX_MODEL_MAP[aux_type]
    fk_column = AUX_FK_MAP[aux_type]

    # 1. Get entity
    entity_result = await db.execute(
        select(model).where(model.id == aux_id)
    )
    entity = entity_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(404, detail=f"{aux_type} {aux_id} 不存在")

    # 2. Determine reference date
    if as_of_date:
        try:
            ref_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, detail=f"日期格式错误: {as_of_date}")
    else:
        ref_date = date.today()

    # 3. Query entries linked to this auxiliary entity
    result = await db.execute(
        select(VoucherEntry, Voucher)
        .join(EntryAuxiliary, EntryAuxiliary.entry_id == VoucherEntry.id)
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .where(
            getattr(EntryAuxiliary, fk_column) == aux_id,
            Voucher.status == "posted",
            Voucher.deleted_at.is_(None),
        )
        .order_by(Voucher.date)
    )

    # 4. Classify into aging buckets
    buckets = {
        "0-30天": {"count": 0, "amount": D("0")},
        "31-90天": {"count": 0, "amount": D("0")},
        "91-180天": {"count": 0, "amount": D("0")},
        "181-365天": {"count": 0, "amount": D("0")},
        ">365天": {"count": 0, "amount": D("0")},
    }

    for entry, voucher in result:
        days = (ref_date - voucher.date).days
        net_amount = entry.debit_amount - entry.credit_amount

        if days <= 30:
            key = "0-30天"
        elif days <= 90:
            key = "31-90天"
        elif days <= 180:
            key = "91-180天"
        elif days <= 365:
            key = "181-365天"
        else:
            key = ">365天"

        buckets[key]["count"] += 1
        buckets[key]["amount"] += net_amount

    bucket_list = [
        AgingBucket(label=k, count=v["count"], amount=v["amount"])
        for k, v in buckets.items()
    ]
    total_count = sum(b.count for b in bucket_list)
    total_amount = sum(b.amount for b in bucket_list)

    return AgingResponse(
        aux_type=aux_type,
        entity={"id": str(entity.id), "code": entity.code, "name": entity.name},
        as_of_date=ref_date,
        buckets=bucket_list,
        total_count=total_count,
        total_amount=total_amount,
    )
