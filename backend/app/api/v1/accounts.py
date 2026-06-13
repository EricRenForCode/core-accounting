"""Chart of accounts routes (§3.5).

GET    /accounts       — flat list (parent_id filter, pagination)
GET    /accounts/tree  — nested tree (for tree picker UI)
POST   /accounts       — create account
PUT    /accounts/{id}  — update account
DELETE /accounts/{id}  — delete (checks for voucher references)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.schemas.account import (
    AccountCreate,
    AccountListResponse,
    AccountSchema,
    AccountTreeResponse,
    AccountUpdate,
)

router = APIRouter()


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
    raise NotImplementedError(
        "list_accounts:\n"
        "1. Build query with optional filters (parent_id, type, is_enabled)\n"
        "2. Order by code ASC\n"
        "3. Paginate (default page_size=100 for account picker)\n"
        "4. Return AccountListResponse"
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
    """
    raise NotImplementedError(
        "get_account_tree:\n"
        "1. SELECT all accounts WHERE is_enabled=TRUE (or filtered)\n"
        "2. Build tree: root nodes have parent_id=NULL\n"
        "3. Recursively attach children to parent nodes\n"
        "4. Return AccountTreeResponse with nested AccountTreeNode"
    )


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
    raise NotImplementedError(
        "create_account:\n"
        "1. Check code uniqueness → 409 if conflict\n"
        "2. If parent_id: verify parent.level + 1 == body.level\n"
        "3. If no parent and level==1: parent_id=NULL\n"
        "4. Create Account(...) and flush\n"
        "5. Return AccountSchema"
    )


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
    raise NotImplementedError(
        "update_account:\n"
        "1. Get account by ID (404 if missing)\n"
        "2. Patch allowed fields: name, is_cash, aux_types, is_quantity, quantity_unit, is_enabled\n"
        "3. Return updated account"
    )


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
    raise NotImplementedError(
        "delete_account:\n"
        "1. Check for child accounts → 409 'Account has sub-accounts'\n"
        "2. Check for voucher_entries with this account_id → 409 ACCOUNT_HAS_VOUCHERS\n"
        "3. Check for account_balances referencing this account\n"
        "4. DELETE account\n"
        "5. Return {message: 'Account deleted'}"
    )
