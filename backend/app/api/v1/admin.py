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

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, hash_password, require_permission, require_role
from app.models.user import User
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
    is_enabled: bool = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:users")),
) -> PaginatedResponse[UserResponse]:
    """List all users (admin only)."""
    raise NotImplementedError(
        "list_users:\n"
        "1. SELECT users JOIN roles\n"
        "2. Optional is_enabled filter\n"
        "3. Paginate\n"
        "4. Return UserResponse items with role_name"
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
    raise NotImplementedError(
        "create_user:\n"
        "1. Check username uniqueness → 409 if exists\n"
        "2. Verify role_id exists → 404 if not\n"
        "3. password_hash = hash_password(body.password)  # bcrypt cost 12\n"
        "4. Create User(username, password_hash, display_name, role_id, is_enabled)\n"
        "5. Return UserResponse"
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:users")),
) -> UserResponse:
    """Update user details (admin only)."""
    raise NotImplementedError(
        "update_user:\n"
        "1. Get user by ID (404 if missing)\n"
        "2. Patch non-None fields from body\n"
        "3. If password provided: re-hash\n"
        "4. Return updated user"
    )


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
    raise NotImplementedError(
        "delete_user:\n"
        "1. Prevent self-deletion → 400\n"
        "2. Get user by ID → 404\n"
        "3. Deactivate (is_enabled=False) or hard delete\n"
        "4. return {message: 'User deleted'}"
    )


# ── Role Management ───────────────────────────────────────────


@router.get("/roles", response_model=list[RoleSchema])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:roles")),
) -> list[RoleSchema]:
    """List all roles with permissions."""
    raise NotImplementedError(
        "list_roles:\n"
        "1. SELECT * FROM roles ORDER BY name\n"
        "2. Return list of RoleSchema"
    )


@router.post("/roles", response_model=RoleSchema, status_code=201)
async def create_role(
    body: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("admin:roles")),
) -> RoleSchema:
    """Create a new role with permission map."""
    raise NotImplementedError(
        "create_role:\n"
        "1. Check name uniqueness\n"
        "2. Create Role(name, permissions=JSONB)\n"
        "3. Return RoleSchema"
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
