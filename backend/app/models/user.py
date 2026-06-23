"""User, Role, and RefreshToken models — §2.10, §2.11"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.voucher import Voucher


class Role(Base, UUIDPrimaryKeyMixin):
    """User role with permission bitmap — §2.10"""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="finance_staff/finance_manager/admin"
    )
    permissions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        comment="Permission flags map e.g. {'voucher:create': true}",
    )

    # ── Relationships ─────────────────────────────────────────
    users: Mapped[List["User"]] = relationship("User", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Application user — §2.10"""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    display_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────
    role: Mapped["Role"] = relationship("Role", back_populates="users")
    created_vouchers: Mapped[List["Voucher"]] = relationship(
        "Voucher",
        foreign_keys="Voucher.creator_id",
        back_populates="creator",
    )
    audited_vouchers: Mapped[List["Voucher"]] = relationship(
        "Voucher",
        foreign_keys="Voucher.auditor_id",
        back_populates="auditor",
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class RefreshToken(Base, UUIDPrimaryKeyMixin):
    """Refresh token storage (§2.11) — stores SHA-256 hash, not raw token."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, comment="SHA-256 hash of refresh token"
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"<RefreshToken user={self.user_id}>"
