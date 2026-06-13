"""Account (科目) model — §2.1"""

import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.voucher import VoucherEntry


class Account(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Chart of accounts — hierarchical tree structure (§2.1)."""

    __tablename__ = "accounts"

    code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, comment="科目编码 e.g. 1001"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="科目名称"
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Parent account for tree hierarchy",
    )
    level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="Hierarchy level 1-4"
    )
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Account type: asset/liability/equity/revenue/expense",
    )
    dc_type: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        comment="Balance direction: D=debit, C=credit",
    )
    is_cash: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether this is a cash/bank account",
    )
    aux_types: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=list,
        comment='Auxiliary核算 types e.g. ["部门","个人"]',
    )
    is_quantity: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether quantity accounting is enabled",
    )
    quantity_unit: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Unit of measure for quantity accounting",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="Whether the account is active"
    )

    # ── Relationships ─────────────────────────────────────────
    parent: Mapped[Optional["Account"]] = relationship(
        "Account", remote_side="Account.id", back_populates="children"
    )
    children: Mapped[List["Account"]] = relationship(
        "Account", back_populates="parent"
    )
    entries: Mapped[List["VoucherEntry"]] = relationship(
        "VoucherEntry", back_populates="account"
    )

    def __repr__(self) -> str:
        return f"<Account {self.code} {self.name}>"
