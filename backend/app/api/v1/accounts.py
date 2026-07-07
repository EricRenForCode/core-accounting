"""Chart of accounts routes (§3.5).

GET    /accounts       — flat list (parent_id filter, pagination)
GET    /accounts/tree  — nested tree (for tree picker UI)
POST   /accounts       — create account
PUT    /accounts/{id}  — update account
DELETE /accounts/{id}  — delete (checks for voucher references)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.account import Account
from app.models.user import User
from app.models.voucher import VoucherEntry
from app.schemas.account import (
    AccountCreate,
    AccountListResponse,
    AccountSchema,
    AccountTreeResponse,
    AccountTreeNode,
    AccountUpdate,
)

router = APIRouter()


async def _invalidate_account_tree_cache() -> None:
    """Drop all cached account-tree variants after a chart mutation."""
    from app.core.cache import cache_delete_pattern

    await cache_delete_pattern("account-tree:*")


@router.get("", response_model=AccountListResponse)
async def list_accounts(
    parent_id: UUID = Query(None),
    type: str = Query(None, description="asset/liability/equity/revenue/expense"),
    is_enabled: bool = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("account:read")),
) -> AccountListResponse:
    """List accounts as a flat list, optionally filtered by parent, type, enabled.

    Root-level accounts have parent_id=NULL.
    """
    # 1. Build base query with optional filters
    conditions = []
    if parent_id is not None:
        conditions.append(Account.parent_id == parent_id)
    if type is not None:
        conditions.append(Account.type == type)
    if is_enabled is not None:
        conditions.append(Account.is_enabled == is_enabled)

    # 2. Count total matching records
    count_query = select(func.count(Account.id))
    if conditions:
        count_query = count_query.where(*conditions)
    total = (await db.execute(count_query)).scalar_one()

    # 3. Fetch page ordered by code ASC
    data_query = select(Account).order_by(Account.code.asc())
    if conditions:
        data_query = data_query.where(*conditions)
    offset = (page - 1) * page_size
    data_query = data_query.offset(offset).limit(page_size)
    result = await db.execute(data_query)
    accounts = result.scalars().all()

    return AccountListResponse(
        accounts=[AccountSchema.model_validate(a) for a in accounts],
        total=total,
    )


@router.get("/tree", response_model=AccountTreeResponse)
async def get_account_tree(
    type: str = Query(None),
    is_enabled: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("account:read")),
) -> AccountTreeResponse:
    """Return the full chart of accounts as a nested tree structure.

    Used by the account picker component in the frontend.
    Cached in Redis for 5 minutes (§P4); invalidated on account mutations.
    """
    from app.core.cache import ACCOUNT_TREE_TTL, cache_get_json, cache_set_json

    cache_key = f"account-tree:{type}:{is_enabled}"
    cached = await cache_get_json(cache_key)
    if cached is not None:
        return AccountTreeResponse.model_validate(cached)

    # 1. Build query with optional filters
    conditions = []
    if type is not None:
        conditions.append(Account.type == type)
    if is_enabled is not None:
        conditions.append(Account.is_enabled == is_enabled)

    query = select(Account).order_by(Account.code.asc())
    if conditions:
        query = query.where(*conditions)
    result = await db.execute(query)
    all_accounts = result.scalars().all()

    # 2. Build lookup dict: id → AccountTreeNode
    node_map: dict[UUID, AccountTreeNode] = {}
    for a in all_accounts:
        node_map[a.id] = AccountTreeNode(
            id=a.id,
            code=a.code,
            name=a.name,
            parent_id=a.parent_id,
            level=a.level,
            type=a.type,
            dc_type=a.dc_type,
            is_cash=a.is_cash,
            aux_types=a.aux_types or [],
            is_quantity=a.is_quantity,
            quantity_unit=a.quantity_unit,
            is_enabled=a.is_enabled,
        )

    # 3. Attach children to parents; roots have parent_id IS NULL
    roots: list[AccountTreeNode] = []
    for a in all_accounts:
        node = node_map[a.id]
        if a.parent_id is None:
            roots.append(node)
        elif a.parent_id in node_map:
            node_map[a.parent_id].children.append(node)

    response = AccountTreeResponse(
        accounts=roots,
        total_count=len(all_accounts),
    )
    await cache_set_json(cache_key, response.model_dump(mode="json"), ACCOUNT_TREE_TTL)
    return response


@router.post("", response_model=AccountSchema, status_code=201)
async def create_account(
    body: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("account:manage")),
) -> AccountSchema:
    """Create a new account in the chart of accounts (admin only).

    Logic:
    1. Validate code uniqueness
    2. If parent_id provided, validate parent exists and level = body.level - 1
    3. Create Account and return
    """
    # 1. Validate code uniqueness
    existing = await db.execute(
        select(Account.id).where(Account.code == body.code)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account code '{body.code}' already exists",
        )

    # 2. Validate parent_id / level consistency
    if body.parent_id is not None:
        parent = await db.execute(
            select(Account).where(Account.id == body.parent_id)
        )
        parent_account = parent.scalar_one_or_none()
        if parent_account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent account '{body.parent_id}' not found",
            )
        if parent_account.level + 1 != body.level:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Level mismatch: parent level is {parent_account.level}, "
                    f"child level must be {parent_account.level + 1}, got {body.level}"
                ),
            )
    else:
        # No parent_id provided
        if body.level != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Level must be 1 when no parent_id is provided",
            )

    # 3. Create Account instance
    account = Account(
        code=body.code,
        name=body.name,
        parent_id=body.parent_id,
        level=body.level,
        type=body.type,
        dc_type=body.dc_type,
        is_cash=body.is_cash,
        aux_types=body.aux_types,
        is_quantity=body.is_quantity,
        quantity_unit=body.quantity_unit,
        is_enabled=body.is_enabled,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    await _invalidate_account_tree_cache()

    return AccountSchema.model_validate(account)


@router.put("/{account_id}", response_model=AccountSchema)
async def update_account(
    account_id: UUID,
    body: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("account:manage")),
) -> AccountSchema:
    """Update account metadata (name, enabled status, aux_types, etc.).

    Does NOT allow changing code, level, type, dc_type, or parent (structural fields).
    """
    # 1. Lookup account by ID
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account '{account_id}' not found",
        )

    # 2. Patch only allowed fields (not code, level, type, dc_type, parent_id)
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    await db.flush()
    await db.refresh(account)
    await _invalidate_account_tree_cache()

    return AccountSchema.model_validate(account)


@router.delete("/{account_id}")
async def delete_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("account:manage")),
) -> dict:
    """Delete an account (only if no voucher entries reference it).

    Checks:
    1. No children exist (parent_id references)
    2. No voucher_entries reference this account
    """
    # 1. Check account exists
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account '{account_id}' not found",
        )

    # 2. Check for child accounts
    children = await db.execute(
        select(func.count(Account.id)).where(Account.parent_id == account_id)
    )
    if children.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account has sub-accounts — delete children first",
        )

    # 3. Check for voucher entries referencing this account
    entries = await db.execute(
        select(func.count(VoucherEntry.id)).where(
            VoucherEntry.account_id == account_id
        )
    )
    if entries.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ACCOUNT_HAS_VOUCHERS",
        )

    # 4. Delete account
    await db.delete(account)
    await db.flush()
    await _invalidate_account_tree_cache()

    return {"message": "Account deleted"}
