"""Auxiliary核算 routes (§3.9).

GET    /auxiliaries/{type}          — archive list (departments/individuals/counterparties/projects)
POST   /auxiliaries/{type}          — create archive entry
PUT    /auxiliaries/{type}/{id}     — update
DELETE /auxiliaries/{type}/{id}     — delete (check references)
GET    /auxiliaries/{type}/{id}/ledger — auxiliary核算明细账
GET    /auxiliaries/{type}/{id}/aging   — 账龄分析
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.period import (
    AgingResponse,
    AuxArchiveCreate,
    AuxArchiveResponse,
    AuxArchiveUpdate,
    AuxLedgerResponse,
)

router = APIRouter()

VALID_AUX_TYPES = {"departments", "individuals", "counterparties", "projects"}


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
    raise NotImplementedError(
        "list_auxiliaries:\n"
        "1. Map aux_type to model: departments→Department, individuals→Individual, etc.\n"
        "2. Query with optional is_enabled filter and search (ILIKE on name/code)\n"
        "3. Paginate and return"
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
    raise NotImplementedError(
        "create_auxiliary:\n"
        "1. Check code uniqueness for the aux type → 409 if conflict\n"
        "2. Create entity (Department/Individual/Counterparty/Project)\n"
        "3. Return AuxArchiveResponse"
    )


@router.put("/{aux_type}/{aux_id}", response_model=AuxArchiveResponse)
async def update_auxiliary(
    aux_type: str,
    aux_id: UUID,
    body: AuxArchiveUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("aux:manage")),
) -> AuxArchiveResponse:
    """Update an auxiliary archive entry."""
    if aux_type not in VALID_AUX_TYPES:
        raise HTTPException(400, f"Invalid aux_type: {aux_type}")
    raise NotImplementedError(
        "update_auxiliary:\n"
        "1. Get entity by aux_type+aux_id (404 if missing)\n"
        "2. Patch fields from body\n"
        "3. Return updated entity"
    )


@router.delete("/{aux_type}/{aux_id}")
async def delete_auxiliary(
    aux_type: str,
    aux_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("aux:manage")),
) -> dict:
    """Delete an auxiliary archive entry (only if no voucher entries reference it)."""
    if aux_type not in VALID_AUX_TYPES:
        raise HTTPException(400, f"Invalid aux_type: {aux_type}")
    raise NotImplementedError(
        "delete_auxiliary:\n"
        "1. Check entry_auxiliaries references → 409 if referenced\n"
        "2. DELETE entity\n"
        "3. Return {message: 'ok'}"
    )


@router.get("/{aux_type}/{aux_id}/ledger", response_model=AuxLedgerResponse)
async def aux_ledger(
    aux_type: str,
    aux_id: UUID,
    period_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ledger:read")),
) -> AuxLedgerResponse:
    """辅助核算明细账 — filtered ledger for a specific auxiliary entity."""
    if aux_type not in VALID_AUX_TYPES:
        raise HTTPException(400, f"Invalid aux_type: {aux_type}")
    raise NotImplementedError(
        "aux_ledger:\n"
        "1. Get entity by aux_type+aux_id\n"
        "2. Query entry_auxiliaries for this entity within the period\n"
        "   - JOIN voucher_entries, vouchers\n"
        "   - WHERE vouchers.period_id=... AND vouchers.status='posted'\n"
        "   - AND entry_auxiliaries.{aux_type}_id = aux_id\n"
        "3. ORDER BY vouchers.date, voucher_entries.row_number\n"
        "4. Calculate running balance\n"
        "5. Return AuxLedgerResponse"
    )


@router.get("/{aux_type}/{aux_id}/aging", response_model=AgingResponse)
async def aux_aging(
    aux_type: str,
    aux_id: UUID,
    as_of_date: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:read")),
) -> AgingResponse:
    """账龄分析 — aging analysis for the auxiliary entity (typically counterparties)."""
    if aux_type not in VALID_AUX_TYPES:
        raise HTTPException(400, f"Invalid aux_type: {aux_type}")
    raise NotImplementedError(
        "aux_aging:\n"
        "1. Get entity\n"
        "2. Calculate current balance for the entity (debits - credits)\n"
        "3. Query all open (unsettled) entries grouped by date ranges:\n"
        "   - 0-30 days, 31-90 days, 91-180 days, 181-365 days, >365 days\n"
        "4. Build AgingBucket for each range\n"
        "5. Return AgingResponse"
    )
