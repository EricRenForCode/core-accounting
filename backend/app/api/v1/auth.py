"""Authentication routes (§3.2).

POST /auth/login     — username+password → JWT pair
POST /auth/refresh   — refresh token → new access token
POST /auth/logout    — revoke refresh token
GET  /auth/me        — current user info
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.core.database import get_db
from app.core.security import (
    auth_scheme,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_permissions,
    hash_password,
    revoke_refresh_token,
    rotate_refresh_token,
    store_refresh_token,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserInfo,
)

router = APIRouter()
settings = Settings()


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Authenticate user and return JWT token pair.

    Logic (§7):
    1. Lookup user by username
    2. Verify password against bcrypt hash
    3. Check user.is_enabled
    4. Build JWT payload with permissions from ROLE_PERMISSIONS matrix
    5. Create access_token (120min) + refresh_token (7d)
    6. Store refresh token hash in refresh_tokens table
    7. Update user.last_login_at
    """
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Permissions from role
    perms = get_user_permissions(user)
    role_name = user.role.name if user.role else ""

    # Create tokens
    access_token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        role=role_name,
        permissions=perms,
    )
    refresh_token = create_refresh_token(
        user_id=str(user.id),
        username=user.username,
    )

    # Store refresh token hash
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    await store_refresh_token(db, refresh_token, user.id, expires_at)

    # Update last_login
    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    await db.flush()

    # Build expires_in (seconds)
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return LoginResponse(
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        ),
        user=UserInfo(
            id=str(user.id),
            username=user.username,
            display_name=user.display_name,
            role=role_name,
            permissions=perms,
            is_enabled=user.is_enabled,
            last_login_at=user.last_login_at,
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a refresh token for a new access token (rotation).

    Logic (§2.11):
    1. Decode and validate the refresh JWT (type=refresh)
    2. Lookup user, verify enabled
    3. Lookup refresh token hash, verify not revoked, not expired
    4. Rotate: revoke old refresh token, issue new access + refresh pair
    """
    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    user_id = payload.get("sub")
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_enabled:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    # Check if refresh token exists and is valid
    import hashlib

    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    rt_result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    rt_record = rt_result.scalar_one_or_none()

    if rt_record is None:
        raise HTTPException(status_code=401, detail="Refresh token revoked or not found")

    # Rotate tokens
    access_token, new_refresh_token = await rotate_refresh_token(
        db, body.refresh_token, user
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    body: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke a refresh token.

    The access token remains valid until expiry but the refresh token is revoked.
    """
    revoked = await revoke_refresh_token(db, body.refresh_token)
    if not revoked:
        raise HTTPException(status_code=404, detail="Token not found or already revoked")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserInfo)
async def get_me(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserInfo:
    """Return the currently authenticated user's profile."""
    from app.core.security import verify_token

    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid access token")

    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == payload["sub"])
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_enabled:
        raise HTTPException(status_code=401, detail="User not found")

    perms = get_user_permissions(user)
    role_name = user.role.name if user.role else ""

    return UserInfo(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        role=role_name,
        permissions=perms,
        is_enabled=user.is_enabled,
        last_login_at=user.last_login_at,
    )
