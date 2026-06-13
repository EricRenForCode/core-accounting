"""Voucher template CRUD routes (§3.4)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.voucher import (
    CreateTemplateRequest,
    UpdateTemplateRequest,
    VoucherTemplateResponse,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[VoucherTemplateResponse])
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_enabled: bool = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[VoucherTemplateResponse]:
    """List voucher templates with optional enabled filter."""
    raise NotImplementedError(
        "list_templates:\n"
        "1. Query VoucherTemplate with optional is_enabled filter\n"
        "2. Paginate and return"
    )


@router.post("", response_model=VoucherTemplateResponse, status_code=201)
async def create_template(
    body: CreateTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoucherTemplateResponse:
    """Create a new voucher template with pre-defined entries."""
    raise NotImplementedError(
        "create_template:\n"
        "1. Validate all account_ids in entries exist\n"
        "2. Create VoucherTemplate(name, description, category, entries=JSONB)\n"
        "3. Return template"
    )


@router.get("/{template_id}", response_model=VoucherTemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoucherTemplateResponse:
    """Get template detail by ID."""
    raise NotImplementedError(
        "get_template: SELECT VoucherTemplate WHERE id=...; 404 if not found"
    )


@router.put("/{template_id}", response_model=VoucherTemplateResponse)
async def update_template(
    template_id: UUID,
    body: UpdateTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoucherTemplateResponse:
    """Update template fields. Only provided fields are patched."""
    raise NotImplementedError(
        "update_template:\n"
        "1. Get template by ID (404 if missing)\n"
        "2. Patch non-None fields from body\n"
        "3. Return updated template"
    )


@router.delete("/{template_id}")
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete a voucher template."""
    raise NotImplementedError(
        "delete_template: DELETE VoucherTemplate WHERE id=...; return {message: 'ok'}"
    )
