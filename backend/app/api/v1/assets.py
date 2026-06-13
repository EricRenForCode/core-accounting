"""Fixed asset routes (§3.11).

GET  /fixed-assets                   — list assets (filter: status, dept_id, category)
POST /fixed-assets                   — create asset
PUT  /fixed-assets/{id}              — update asset
POST /fixed-assets/{id}/depreciate   — single depreciation
POST /fixed-assets/depreciate-batch  — batch depreciation
POST /fixed-assets/{id}/dispose      — dispose asset
GET  /fixed-assets/reports           — depreciation summary report
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("")
async def list_assets(
    status: str = Query(None, description="in_use/disposed/cleared"),
    dept_id: UUID = Query(None),
    category: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> PaginatedResponse[dict]:
    """List fixed assets with filtering."""
    raise NotImplementedError(
        "list_assets:\n"
        "1. Query FixedAsset with optional status, dept_id, category filters\n"
        "2. ORDER BY code\n"
        "3. Paginate"
    )


@router.post("", status_code=201)
async def create_asset(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> dict:
    """Create a new fixed asset card.

    Body: {code, name, category, purchase_date, purchase_amount, salvage_value,
           useful_life_months, depreciation_method, dept_id}

    On creation, auto-calculate:
    - monthly_depreciation based on method
    - net_value = purchase_amount
    """
    raise NotImplementedError(
        "create_asset:\n"
        "1. Validate code uniqueness\n"
        "2. Calculate monthly_depreciation based on method:\n"
        "   - straight: (purchase_amount - salvage_value) / useful_life_months\n"
        "   - double_declining: (2 / useful_life_months) * (purchase_amount - accumulated)\n"
        "   - sum_of_years: see §7\n"
        "3. Set net_value = purchase_amount, accumulated_depreciation = 0\n"
        "4. Create FixedAsset and return"
    )


@router.put("/{asset_id}")
async def update_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> dict:
    """Update asset card information (name, dept_id, etc.).

    Does NOT recalculate depreciation; that requires explicit depreciate call.
    """
    raise NotImplementedError(
        "update_asset:\n"
        "1. Get asset by ID (404 if missing)\n"
        "2. Check asset.status != 'disposed' → 409 if disposed\n"
        "3. Patch allowed fields\n"
        "4. Return updated asset"
    )


@router.post("/{asset_id}/depreciate")
async def depreciate_single(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> dict:
    """Execute one month of depreciation for a single asset.

    Updates accumulated_depreciation and net_value.
    Auto-generates a depreciation voucher entry (requires period context).
    """
    raise NotImplementedError(
        "depreciate_single:\n"
        "1. Get asset, verify status='in_use'\n"
        "2. Calculate this month's depreciation (consider partial months)\n"
        "3. accumulated_depreciation += monthly_depreciation\n"
        "4. net_value = purchase_amount - accumulated_depreciation\n"
        "5. If net_value <= salvage_value: cap at salvage_value\n"
        "6. Create depreciation voucher entry (debit: depreciation expense, credit: accumulated depreciation)\n"
        "7. Return {asset: ..., depreciation_amount: ..., new_net_value: ...}"
    )


@router.post("/depreciate-batch")
async def depreciate_batch(
    period_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> dict:
    """Batch depreciate all in-use assets for a period.

    Auto-creates a consolidated depreciation voucher.
    """
    raise NotImplementedError(
        "depreciate_batch:\n"
        "1. Query all FixedAsset WHERE status='in_use'\n"
        "2. For each asset: run depreciate_single logic\n"
        "3. Aggregate depreciation entries into one voucher\n"
        "4. Auto-post the voucher\n"
        "5. Return {count: N, total_depreciation: ..., voucher_no: ...}"
    )


@router.post("/{asset_id}/dispose")
async def dispose_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> dict:
    """Dispose (清理) a fixed asset.

    Calculates gain/loss on disposal and creates appropriate voucher entries.
    """
    raise NotImplementedError(
        "dispose_asset:\n"
        "1. Get asset, verify status='in_use'\n"
        "2. Calculate net book value = purchase_amount - accumulated_depreciation\n"
        "3. Create disposal voucher:\n"
        "   - Debit: accumulated depreciation (to clear)\n"
        "   - Credit/Debit: gain/loss on disposal (difference)\n"
        "   - Credit: fixed asset (purchase_amount)\n"
        "4. Set status='disposed'\n"
        "5. Return {asset, disposal_voucher_no, gain_loss_amount}"
    )


@router.get("/reports")
async def asset_reports(
    period_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> dict:
    """Generate fixed asset reports (depreciation summary, asset register, etc.)."""
    raise NotImplementedError(
        "asset_reports:\n"
        "1. Depreciation summary: group by category, sum monthly depreciation\n"
        "2. Asset register: full list with book values\n"
        "3. Disposal log: disposed assets with gain/loss\n"
        "4. Return multi-section report"
    )
