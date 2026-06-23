"""Fixed Assets routes (§3.11).

GET    /fixed-assets               — asset list
POST   /fixed-assets               — create asset
PUT    /fixed-assets/{id}          — update asset
POST   /fixed-assets/{id}/depreciate    — single depreciation
POST   /fixed-assets/depreciate-batch   — batch depreciation
POST   /fixed-assets/{id}/dispose       — dispose asset
GET    /fixed-assets/reports            — asset reports
"""

import uuid as _uuid
import math
from datetime import date as date_type, datetime
from decimal import Decimal as D

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.models.asset import FixedAsset
from app.models.period import Period
from app.schemas.cashier import (
    AssetReportResponse,
    DepreciateBatchRequest,
    DepreciateRequest,
    DepreciateResponse,
    DisposeRequest,
    FixedAssetCreate,
    FixedAssetResponse,
    FixedAssetUpdate,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()


def _calc_monthly_depreciation(
    purchase_amount: D,
    salvage_value: D,
    useful_life_months: int,
    method: str,
    accumulated: D = D("0"),
    month_number: int = 1,
) -> D:
    """Calculate monthly depreciation amount based on method."""
    if method == "straight":
        # (原值 - 残值) / 使用月数
        return (purchase_amount - salvage_value) / useful_life_months

    elif method == "double_declining":
        # 双倍余额递减法: 2 / 使用月数 * (原值 - 累计折旧)
        rate = D("2") / useful_life_months
        return (purchase_amount - accumulated) * rate

    elif method == "sum_of_years":
        # 年数总和法 — convert months to years for the formula
        total_years = int(math.ceil(useful_life_months / 12))
        year_sum = total_years * (total_years + 1) // 2
        current_year = (month_number - 1) // 12 + 1
        remaining_years = total_years - current_year + 1
        yearly_depr = (purchase_amount - salvage_value) * D(str(remaining_years)) / D(str(year_sum))
        return yearly_depr / 12

    return D("0")


# ── List ────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[FixedAssetResponse])
async def list_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    dept_id: _uuid.UUID = Query(None),
    category: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> PaginatedResponse[FixedAssetResponse]:
    """List fixed assets with optional filters."""
    q = select(FixedAsset)
    count_q = select(func.count(FixedAsset.id))

    if status:
        q = q.where(FixedAsset.status == status)
        count_q = count_q.where(FixedAsset.status == status)
    if dept_id:
        q = q.where(FixedAsset.dept_id == dept_id)
        count_q = count_q.where(FixedAsset.dept_id == dept_id)
    if category:
        q = q.where(FixedAsset.category == category)
        count_q = count_q.where(FixedAsset.category == category)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    q = q.order_by(FixedAsset.code).offset(offset).limit(page_size)
    result = await db.execute(q)
    items = list(result.scalars().all())

    return PaginatedResponse(
        items=[FixedAssetResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=((total + page_size - 1) // page_size) if total > 0 else 0,
    )


# ── Create ──────────────────────────────────────────────────────


@router.post("", response_model=FixedAssetResponse, status_code=201)
async def create_asset(
    body: FixedAssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> FixedAssetResponse:
    """Create a new fixed asset card with initial depreciation calculation."""
    # Check code uniqueness
    existing = await db.execute(
        select(FixedAsset).where(FixedAsset.code == body.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"资产编码 {body.code} 已存在")

    # Calculate initial depreciation
    monthly = _calc_monthly_depreciation(
        body.purchase_amount,
        body.salvage_value,
        body.useful_life_months,
        body.depreciation_method,
    )
    net_value = body.purchase_amount

    asset = FixedAsset(
        code=body.code,
        name=body.name,
        category=body.category,
        purchase_date=body.purchase_date,
        purchase_amount=body.purchase_amount,
        salvage_value=body.salvage_value,
        useful_life_months=body.useful_life_months,
        depreciation_method=body.depreciation_method,
        monthly_depreciation=monthly,
        accumulated_depreciation=D("0"),
        net_value=net_value,
        status="in_use",
        dept_id=body.dept_id,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    return FixedAssetResponse.model_validate(asset)


# ── Update ──────────────────────────────────────────────────────


@router.put("/{asset_id}", response_model=FixedAssetResponse)
async def update_asset(
    asset_id: _uuid.UUID,
    body: FixedAssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> FixedAssetResponse:
    """Update a fixed asset card."""
    result = await db.execute(
        select(FixedAsset).where(FixedAsset.id == asset_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "资产不存在")

    # Code uniqueness check
    if body.code and body.code != asset.code:
        dup = await db.execute(
            select(FixedAsset).where(
                FixedAsset.code == body.code, FixedAsset.id != asset_id
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(409, f"资产编码 {body.code} 已存在")

    update_data = body.model_dump(exclude_unset=True)
    old_purchase = asset.purchase_amount
    old_salvage = asset.salvage_value
    old_months = asset.useful_life_months
    old_method = asset.depreciation_method

    for key, value in update_data.items():
        setattr(asset, key, value)

    # Recalculate depreciation if relevant fields changed
    if any(k in update_data for k in [
        "purchase_amount", "salvage_value", "useful_life_months", "depreciation_method"
    ]):
        asset.monthly_depreciation = _calc_monthly_depreciation(
            asset.purchase_amount,
            asset.salvage_value,
            asset.useful_life_months,
            asset.depreciation_method,
            asset.accumulated_depreciation,
        )

    await db.commit()
    await db.refresh(asset)

    return FixedAssetResponse.model_validate(asset)


# ── Single Depreciation ────────────────────────────────────────


@router.post("/{asset_id}/depreciate", response_model=DepreciateResponse)
async def depreciate_asset(
    asset_id: _uuid.UUID,
    body: DepreciateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> DepreciateResponse:
    """Depreciate a single asset for one period."""
    result = await db.execute(
        select(FixedAsset).where(FixedAsset.id == asset_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "资产不存在")
    if asset.status != "in_use":
        raise HTTPException(400, "该资产不在使用中，无法折旧")
    if asset.net_value <= asset.salvage_value:
        raise HTTPException(400, "资产净值已等于或低于残值，无需折旧")

    # Calculate months since purchase (estimate month_number)
    months_used = asset.accumulated_depreciation / asset.monthly_depreciation if asset.monthly_depreciation > 0 else 0
    month_num = int(months_used) + 1

    monthly = _calc_monthly_depreciation(
        asset.purchase_amount,
        asset.salvage_value,
        asset.useful_life_months,
        asset.depreciation_method,
        asset.accumulated_depreciation,
        month_num,
    )

    # Cap at net_value - salvage_value
    max_depr = asset.net_value - asset.salvage_value
    if monthly > max_depr:
        monthly = max_depr

    asset.accumulated_depreciation += monthly
    asset.net_value = asset.purchase_amount - asset.accumulated_depreciation
    asset.monthly_depreciation = monthly

    await db.commit()
    await db.refresh(asset)

    return DepreciateResponse(
        asset_id=asset.id,
        asset_name=asset.name,
        monthly_depreciation=monthly,
        accumulated_depreciation=asset.accumulated_depreciation,
        net_value=asset.net_value,
    )


# ── Batch Depreciation ─────────────────────────────────────────


@router.post("/depreciate-batch", response_model=list[DepreciateResponse])
async def depreciate_batch(
    body: DepreciateBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> list[DepreciateResponse]:
    """Depreciate all in-use assets for a period."""
    result = await db.execute(
        select(FixedAsset).where(FixedAsset.status == "in_use")
    )
    assets = list(result.scalars().all())

    responses: list[DepreciateResponse] = []
    for asset in assets:
        if asset.net_value <= asset.salvage_value:
            continue

        months_used = asset.accumulated_depreciation / asset.monthly_depreciation if asset.monthly_depreciation > 0 else 0
        month_num = int(months_used) + 1

        monthly = _calc_monthly_depreciation(
            asset.purchase_amount,
            asset.salvage_value,
            asset.useful_life_months,
            asset.depreciation_method,
            asset.accumulated_depreciation,
            month_num,
        )

        max_depr = asset.net_value - asset.salvage_value
        if monthly > max_depr:
            monthly = max_depr

        asset.accumulated_depreciation += monthly
        asset.net_value = asset.purchase_amount - asset.accumulated_depreciation
        asset.monthly_depreciation = monthly

        responses.append(DepreciateResponse(
            asset_id=asset.id,
            asset_name=asset.name,
            monthly_depreciation=monthly,
            accumulated_depreciation=asset.accumulated_depreciation,
            net_value=asset.net_value,
        ))

    await db.commit()
    return responses


# ── Dispose ─────────────────────────────────────────────────────


@router.post("/{asset_id}/dispose", response_model=FixedAssetResponse)
async def dispose_asset(
    asset_id: _uuid.UUID,
    body: DisposeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> FixedAssetResponse:
    """Dispose (retire/sell) a fixed asset."""
    result = await db.execute(
        select(FixedAsset).where(FixedAsset.id == asset_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "资产不存在")
    if asset.status != "in_use":
        raise HTTPException(400, "该资产已处置或已清理")

    # Calculate gain/loss: disposal_amount - net_value
    # This would generate a corresponding voucher in production
    asset.status = "disposed"
    # Store disposal info could go in a disposal record

    await db.commit()
    await db.refresh(asset)

    return FixedAssetResponse.model_validate(asset)


# ── Reports ─────────────────────────────────────────────────────


@router.get("/reports", response_model=AssetReportResponse)
async def asset_reports(
    period_id: _uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("assets:manage")),
) -> AssetReportResponse:
    """Generate fixed asset summary report."""
    from collections import defaultdict

    # Get period
    period_result = await db.execute(
        select(Period).where(Period.id == period_id)
    )
    period = period_result.scalar_one_or_none()
    if not period:
        raise HTTPException(404, "会计期间不存在")

    # Get all assets
    result = await db.execute(select(FixedAsset))
    assets = list(result.scalars().all())

    total_original = sum((a.purchase_amount for a in assets), D("0"))
    total_depr = sum((a.accumulated_depreciation for a in assets), D("0"))
    total_net = sum((a.net_value for a in assets), D("0"))

    # By category
    by_cat: dict[str, dict] = defaultdict(lambda: {
        "category": "", "count": 0, "original": D("0"),
        "depreciation": D("0"), "net": D("0"),
    })
    for a in assets:
        c = by_cat[a.category]
        c["category"] = a.category
        c["count"] += 1
        c["original"] += a.purchase_amount
        c["depreciation"] += a.accumulated_depreciation
        c["net"] += a.net_value

    # By status
    by_stat: dict[str, dict] = defaultdict(lambda: {
        "status": "", "count": 0, "net_value": D("0"),
    })
    for a in assets:
        s = by_stat[a.status]
        s["status"] = a.status
        s["count"] += 1
        s["net_value"] += a.net_value

    return AssetReportResponse(
        period={"year": period.year, "month": period.month},
        total_assets=len(assets),
        total_original_value=total_original,
        total_accumulated_depreciation=total_depr,
        total_net_value=total_net,
        by_category=[
            {k: str(v) if isinstance(v, D) else v for k, v in c.items()}
            for c in by_cat.values()
        ],
        by_status=[
            {k: str(v) if isinstance(v, D) else v for k, v in s.items()}
            for s in by_stat.values()
        ],
    )
