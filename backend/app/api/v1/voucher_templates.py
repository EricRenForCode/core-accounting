"""Voucher template CRUD routes (§3.4)."""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.models.voucher import VoucherTemplate
from app.models.account import Account
from app.schemas.common import PaginatedResponse
from app.schemas.voucher import (
    CreateTemplateRequest,
    UpdateTemplateRequest,
    VoucherTemplateResponse,
)

router = APIRouter()


def _template_to_response(t: VoucherTemplate) -> VoucherTemplateResponse:
    """Convert VoucherTemplate ORM → response schema."""
    entries = t.entries or []
    # entries stored as JSONB list of {account_id, summary, dc_side, auxiliaries}
    return VoucherTemplateResponse(
        id=t.id,
        name=t.name,
        description=t.description,
        category=t.category,
        entries=[
            {
                "account_id": str(e.get("account_id", "")) if e.get("account_id") else None,
                "summary": e.get("summary", ""),
                "dc_side": e.get("dc_side", "debit"),
                "auxiliaries": e.get("auxiliaries", []),
            }
            for e in entries
        ],
        is_enabled=t.is_enabled,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("", response_model=PaginatedResponse[VoucherTemplateResponse])
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_enabled: bool = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> PaginatedResponse[VoucherTemplateResponse]:
    """List voucher templates with optional enabled filter."""
    query = select(VoucherTemplate)
    count_q = select(func.count(VoucherTemplate.id))

    if is_enabled is not None:
        query = query.where(VoucherTemplate.is_enabled == is_enabled)
        count_q = count_q.where(VoucherTemplate.is_enabled == is_enabled)

    total_result = await db.execute(count_q)
    total: int = total_result.scalar_one()

    query = query.order_by(VoucherTemplate.name)
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    templates = result.scalars().all()

    return PaginatedResponse(
        items=[_template_to_response(t) for t in templates],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.post("", response_model=VoucherTemplateResponse, status_code=201)
async def create_template(
    body: CreateTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> VoucherTemplateResponse:
    """Create a new voucher template with pre-defined entries."""
    # Validate all account_ids exist
    account_ids = {
        e.account_id for e in body.entries if e.account_id
    }
    if account_ids:
        acct_result = await db.execute(
            select(Account).where(Account.id.in_(account_ids))
        )
        found = {a.id for a in acct_result.scalars().all()}
        missing = account_ids - found
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"科目不存在: {missing}",
            )

    template = VoucherTemplate(
        name=body.name,
        description=body.description,
        category=body.category,
        entries=[
            {
                "account_id": str(e.account_id),
                "summary": e.summary,
                "dc_side": e.dc_side,
                "auxiliaries": [
                    {
                        "aux_type": a.aux_type,
                        "department_id": str(a.department_id) if a.department_id else None,
                        "individual_id": str(a.individual_id) if a.individual_id else None,
                        "counterparty_id": str(a.counterparty_id) if a.counterparty_id else None,
                        "project_id": str(a.project_id) if a.project_id else None,
                    }
                    for a in e.auxiliaries
                ],
            }
            for e in body.entries
        ],
        is_enabled=body.is_enabled,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)

    return _template_to_response(template)


@router.get("/{template_id}", response_model=VoucherTemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> VoucherTemplateResponse:
    """Get template detail by ID."""
    result = await db.execute(
        select(VoucherTemplate).where(VoucherTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return _template_to_response(template)


@router.put("/{template_id}", response_model=VoucherTemplateResponse)
async def update_template(
    template_id: UUID,
    body: UpdateTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> VoucherTemplateResponse:
    """Update template fields. Only provided fields are patched."""
    result = await db.execute(
        select(VoucherTemplate).where(VoucherTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    if body.name is not None:
        template.name = body.name
    if body.description is not None:
        template.description = body.description
    if body.category is not None:
        template.category = body.category
    if body.is_enabled is not None:
        template.is_enabled = body.is_enabled
    if body.entries is not None:
        # Validate account_ids
        account_ids = {
            e.account_id for e in body.entries if e.account_id
        }
        if account_ids:
            acct_result = await db.execute(
                select(Account).where(Account.id.in_(account_ids))
            )
            found = {a.id for a in acct_result.scalars().all()}
            missing = account_ids - found
            if missing:
                raise HTTPException(
                    status_code=404,
                    detail=f"科目不存在: {missing}",
                )
        template.entries = [
            {
                "account_id": str(e.account_id),
                "summary": e.summary,
                "dc_side": e.dc_side,
                "auxiliaries": [
                    {
                        "aux_type": a.aux_type,
                        "department_id": str(a.department_id) if a.department_id else None,
                        "individual_id": str(a.individual_id) if a.individual_id else None,
                        "counterparty_id": str(a.counterparty_id) if a.counterparty_id else None,
                        "project_id": str(a.project_id) if a.project_id else None,
                    }
                    for a in e.auxiliaries
                ],
            }
            for e in body.entries
        ]

    await db.flush()
    await db.refresh(template)
    return _template_to_response(template)


@router.delete("/{template_id}")
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> dict:
    """Delete a voucher template."""
    result = await db.execute(
        select(VoucherTemplate).where(VoucherTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    await db.delete(template)
    return {"message": "模板已删除"}
