"""System administration routes (§3.13).

GET/POST      /admin/users         — list/create users
PUT/DELETE    /admin/users/{id}    — update/delete user
GET/POST      /admin/roles         — list/create roles
GET           /admin/audit-logs    — view audit trail
POST          /admin/backup        — manual backup
GET           /admin/backups       — list backups
GET           /admin/params        — system parameters
PUT           /admin/params        — update parameters
"""

import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user, hash_password, require_permission, require_role
from app.models.user import Role, User
from app.schemas.common import PaginatedResponse
from app.schemas.period import (
    AuditLogFilter,
    AuditLogResponse,
    BackupResponse,
    RoleCreate,
    RoleSchema,
    RoleUpdate,
    SystemParams,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


# ── User Management ───────────────────────────────────────────


@router.get("/users", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_enabled: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:users")),
) -> PaginatedResponse[UserResponse]:
    """List all users (admin only)."""
    query = (
        select(User)
        .options(selectinload(User.role))
        .order_by(User.created_at.desc())
    )

    if is_enabled is not None:
        query = query.where(User.is_enabled == is_enabled)

    count_query = select(func.count()).select_from(User)
    if is_enabled is not None:
        count_query = count_query.where(User.is_enabled == is_enabled)

    total_result = await db.execute(count_query)
    total: int = total_result.scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    users = result.scalars().all()

    items = [
        UserResponse(
            id=u.id,
            username=u.username,
            display_name=u.display_name,
            role_id=u.role_id,
            role_name=u.role.name if u.role else None,
            is_enabled=u.is_enabled,
            last_login_at=u.last_login_at,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in users
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


def _user_to_response(u: User) -> UserResponse:
    return UserResponse(
        id=u.id,
        username=u.username,
        display_name=u.display_name,
        role_id=u.role_id,
        role_name=u.role.name if u.role else None,
        is_enabled=u.is_enabled,
        last_login_at=u.last_login_at,
        created_at=u.created_at,
        updated_at=u.updated_at,
    )


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:users")),
) -> UserResponse:
    """Create a new user (admin only).

    Hashes password with bcrypt, assigns role.
    """
    # 1. Check username uniqueness
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"用户名 '{body.username}' 已存在",
        )

    # 2. Verify role_id exists
    role_result = await db.execute(select(Role).where(Role.id == body.role_id))
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"角色不存在",
        )

    # 3. Hash password and create user
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role_id=body.role_id,
        is_enabled=body.is_enabled,
    )
    db.add(user)
    await db.flush()

    # Reload with role relationship
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user.id)
    )
    user = result.scalar_one()

    return _user_to_response(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:users")),
) -> UserResponse:
    """Update user details (admin only)."""
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    if body.display_name is not None:
        user.display_name = body.display_name
    if body.role_id is not None:
        role_result = await db.execute(select(Role).where(Role.id == body.role_id))
        if not role_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="角色不存在",
            )
        user.role_id = body.role_id
    if body.is_enabled is not None:
        user.is_enabled = body.is_enabled
    if body.password is not None:
        user.password_hash = hash_password(body.password)

    await db.flush()

    # Reload with role relationship
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user.id)
    )
    user = result.scalar_one()

    return _user_to_response(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:users")),
) -> dict:
    """Soft-delete or fully delete a user (admin only).

    Cannot delete self.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账号",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # Soft-delete: disable the user instead of removing from DB
    user.is_enabled = False
    await db.flush()

    return {"message": "用户已删除"}


# ── Role Management ───────────────────────────────────────────


@router.get("/roles", response_model=list[RoleSchema])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:roles")),
) -> list[RoleSchema]:
    """List all roles with permissions."""
    result = await db.execute(select(Role).order_by(Role.name))
    roles = result.scalars().all()

    return [
        RoleSchema(
            id=r.id,
            name=r.name,
            permissions=r.permissions or {},
        )
        for r in roles
    ]


@router.post("/roles", response_model=RoleSchema, status_code=201)
async def create_role(
    body: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:roles")),
) -> RoleSchema:
    """Create a new role with permission map."""
    # Check name uniqueness
    existing = await db.execute(select(Role).where(Role.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"角色名称 '{body.name}' 已存在",
        )

    role = Role(
        name=body.name,
        permissions=body.permissions,
    )
    db.add(role)
    await db.flush()

    return RoleSchema(
        id=role.id,
        name=role.name,
        permissions=role.permissions or {},
    )


# ── Audit Logs ────────────────────────────────────────────────


@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogResponse])
async def list_audit_logs(
    filters: AuditLogFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:audit-log")),
) -> PaginatedResponse[AuditLogResponse]:
    """View audit trail with filters: user_id, action, resource_type, date range."""
    raise NotImplementedError(
        "list_audit_logs:\n"
        "1. Query AuditLog with optional filters\n"
        "2. ORDER BY created_at DESC (use idx_audit_logs_created)\n"
        "3. Paginate\n"
        "4. Return AuditLogResponse items"
    )


# ── Backup Management ─────────────────────────────────────────


@router.post("/backup")
async def create_backup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:backup")),
) -> dict:
    """Trigger a manual database backup.

    Run pg_dump to a backup directory.
    """
    raise NotImplementedError(
        "create_backup:\n"
        "1. Execute pg_dump (subprocess) with connection params from settings\n"
        "2. Compress output (gzip)\n"
        "3. Store in backups/ directory with timestamp\n"
        "4. Return {id, name, size, created_at}"
    )


@router.get("/backups", response_model=list[BackupResponse])
async def list_backups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:backup")),
) -> list[BackupResponse]:
    """List available backups."""
    raise NotImplementedError(
        "list_backups:\n"
        "1. List files in backups/ directory\n"
        "2. Return file metadata (name, size, created_at)"
    )


# ── System Parameters ─────────────────────────────────────────


@router.get("/params", response_model=SystemParams)
async def get_params(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SystemParams:
    """Get system parameters (company name, fiscal year start, etc.)."""
    raise NotImplementedError(
        "get_params:\n"
        "1. Read from system_params table or config\n"
        "2. Return {company_name, fiscal_year_start_month, default_currency, ...}"
    )


@router.put("/params", response_model=SystemParams)
async def update_params(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:users")),
) -> SystemParams:
    """Update system parameters."""
    raise NotImplementedError(
        "update_params:\n"
        "1. Validate and persist parameter updates\n"
        "2. Return updated params"
    )
