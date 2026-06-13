"""Authentication request/response schemas (§3.2)."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """POST /auth/login request body."""

    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token TTL in seconds")


class RefreshRequest(BaseModel):
    """POST /auth/refresh request body."""

    refresh_token: str


class UserInfo(BaseModel):
    """GET /auth/me response — current user info."""

    id: str
    username: str
    display_name: str
    role: str
    permissions: list[str]
    is_enabled: bool
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    """Full login response: tokens + user info."""

    tokens: TokenResponse
    user: UserInfo


class LogoutRequest(BaseModel):
    """POST /auth/logout request body."""

    refresh_token: str
