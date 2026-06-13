"""Authentication & Authorization — JWT, password hashing, RBAC, refresh tokens.

Implements:
- JWT create_access_token / create_refresh_token / decode_token
- bcrypt password hashing (cost factor 12)
- get_current_user — FastAPI dependency from Bearer token
- require_role(role_name) — dependency factory
- require_permission(perm) — dependency factory
- 23-permission RBAC matrix (§2.10)
- Refresh token rotation (hash storage, revoke-on-use)
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.database import get_db
from app.models.user import RefreshToken, Role, User

__all__ = [
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "verify_token",
    "hash_password",
    "verify_password",
    "get_current_user",
    "require_role",
    "require_permission",
    "store_refresh_token",
    "revoke_refresh_token",
    "rotate_refresh_token",
    "ROLE_PERMISSIONS",
]

# ── Password Hashing ──────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt (cost factor 12)."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────

settings = Settings()
security_scheme = HTTPBearer()


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    permissions: list[str],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a short-lived access JWT.

    Payload: { sub, username, role, permissions, type: "access", exp, iat, jti }
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "permissions": permissions,
        "type": "access",
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    user_id: str,
    username: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a long-lived refresh JWT.

    Payload: { sub, username, type: "refresh", exp, iat, jti }
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
    payload = {
        "sub": user_id,
        "username": username,
        "type": "refresh",
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises JWTError on failure."""
    return jwt.decode(
        token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
    )


def verify_token(token: str) -> Optional[dict[str, Any]]:
    """Verify a JWT and return payload, or None if invalid/expired."""
    try:
        payload = decode_token(token)
        if payload.get("type") == "access":
            return payload
        return None
    except JWTError:
        return None


# ── get_current_user ──────────────────────────────────────────


class OAuth2PasswordBearerCookie(HTTPBearer):
    """Overridden to also accept token from cookies (optional)."""

    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        # Try Bearer header first
        try:
            return await super().__call__(request)
        except HTTPException:
            # Fallback: check cookie
            token = request.cookies.get("access_token")
            if token:
                return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            raise


auth_scheme = OAuth2PasswordBearerCookie()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate current user from Bearer token.

    Raises 401 if token is invalid, expired, or user is disabled/deleted.
    """
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
        )

    return user


# ── RBAC ──────────────────────────────────────────────────────

# Full 23-permission matrix from §2.10
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "finance_staff": [
        "voucher:create",
        "voucher:edit:own",
        "voucher:delete:draft",
        "account:read",
        "ledger:read",
        "report:read",
        "report:export",
        "aux:manage",
        "cashier:use",
        "ai:use",
    ],
    "finance_manager": [
        "voucher:create",
        "voucher:edit:own",
        "voucher:edit:any",
        "voucher:delete:draft",
        "voucher:audit",
        "voucher:unaudit",
        "voucher:post",
        "voucher:reverse",
        "account:read",
        "ledger:read",
        "report:read",
        "report:export",
        "period:close",
        "aux:manage",
        "cashier:use",
        "assets:manage",
        "ai:use",
    ],
    "admin": [
        "voucher:create",
        "voucher:edit:own",
        "voucher:edit:any",
        "voucher:delete:draft",
        "voucher:audit",
        "voucher:unaudit",
        "voucher:post",
        "voucher:reverse",
        "account:read",
        "account:manage",
        "ledger:read",
        "report:read",
        "report:export",
        "period:close",
        "period:reopen",
        "aux:manage",
        "cashier:use",
        "assets:manage",
        "ai:use",
        "admin:users",
        "admin:roles",
        "admin:backup",
        "admin:audit-log",
    ],
}


def get_user_permissions(user: User) -> list[str]:
    """Resolve effective permissions for a user from their role."""
    if user.role and user.role.permissions:
        # If role has explicit permission map, use it
        return [
            perm
            for perm, granted in user.role.permissions.items()
            if granted
        ]
    # Fallback to role-name-based lookup
    return ROLE_PERMISSIONS.get(user.role.name if user.role else "", [])


def require_role(required_role: str) -> Callable:
    """Dependency factory: require a specific role.

    Usage:
        router.post("/vouchers/{id}/audit", dependencies=[Depends(require_role("finance_manager"))])
    """

    async def _check_role(
        credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
        db: AsyncSession = Depends(get_db),
    ) -> bool:
        token = credentials.credentials
        payload = verify_token(token)
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_role = payload.get("role", "")
        if user_role != required_role and user_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: role '{required_role}' required",
            )
        return True

    return _check_role


def require_permission(permission: str) -> Callable:
    """Dependency factory: require a specific permission.

    Usage:
        router.post("/vouchers/{id}/audit",
                     dependencies=[Depends(require_permission("voucher:audit"))])
    """

    async def _check_permission(
        credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    ) -> bool:
        token = credentials.credentials
        payload = verify_token(token)
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        perms = payload.get("permissions", [])
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: '{permission}' required",
            )
        return True

    return _check_permission


# ── Refresh Token Management ──────────────────────────────────

def _hash_token(raw_token: str) -> str:
    """SHA-256 hash a raw token for storage."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def store_refresh_token(
    db: AsyncSession,
    raw_token: str,
    user_id: uuid.UUID,
    expires_at: datetime,
) -> RefreshToken:
    """Store the SHA-256 hash of a refresh token in the database."""
    token_record = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw_token),
        expires_at=expires_at,
    )
    db.add(token_record)
    await db.flush()
    return token_record


async def revoke_refresh_token(
    db: AsyncSession,
    raw_token: str,
) -> bool:
    """Revoke a refresh token by its raw value.

    Returns True if token was found and revoked, False otherwise.
    """
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    token_record = result.scalar_one_or_none()
    if token_record:
        token_record.revoked_at = datetime.now(timezone.utc)
        await db.flush()
        return True
    return False


async def rotate_refresh_token(
    db: AsyncSession,
    old_raw_token: str,
    user: User,
) -> tuple[str, str]:
    """Rotate refresh token: revoke old, issue new access + refresh.

    Returns (access_token, refresh_token) tuple.
    """
    # Revoke old refresh token
    await revoke_refresh_token(db, old_raw_token)

    # Resolve user permissions
    perms = get_user_permissions(user)

    # Issue new tokens
    access_token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        role=user.role.name if user.role else "",
        permissions=perms,
    )
    refresh_token = create_refresh_token(
        user_id=str(user.id),
        username=user.username,
    )

    # Store new refresh token hash
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    await store_refresh_token(db, refresh_token, user.id, expires_at)

    return access_token, refresh_token
