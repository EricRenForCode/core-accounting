"""Period, CarryForward, and CarryTemplate models — §2.6, §2.7, §2.8"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.voucher import Voucher
    from app.models.user import User


class Period(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """会计期间 — §2.6"""

    __tablename__ = "periods"

    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="1-12")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", comment="open/closed"
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    closed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────
    vouchers: Mapped[List["Voucher"]] = relationship(
        "Voucher", back_populates="period"
    )
    carry_forwards: Mapped[List["CarryForward"]] = relationship(
        "CarryForward", back_populates="period"
    )
    account_balances: Mapped[List["AccountBalance"]] = relationship(
        "AccountBalance", back_populates="period"
    )

    # ── Constraints ───────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_period_year_month"),
        CheckConstraint(
            "month BETWEEN 1 AND 12", name="ck_period_month_range"
        ),
    )

    def __repr__(self) -> str:
        return f"<Period {self.year}-{self.month:02d} [{self.status}]>"


class AccountBalance(Base, UUIDPrimaryKeyMixin):
    """科目余额快照 — §2.9"""

    __tablename__ = "account_balances"

    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("periods.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )

    opening_debit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, nullable=False, comment="期初借方"
    )
    opening_credit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, nullable=False, comment="期初贷方"
    )
    current_debit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, nullable=False, comment="本期借方"
    )
    current_credit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, nullable=False, comment="本期贷方"
    )
    closing_debit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, nullable=False, comment="期末借方"
    )
    closing_credit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, nullable=False, comment="期末贷方"
    )

    # ── Relationships ─────────────────────────────────────────
    period: Mapped["Period"] = relationship("Period", back_populates="account_balances")
    account: Mapped["Account"] = relationship("Account")

    # ── Constraints ───────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("period_id", "account_id", name="uq_balance_period_account"),
        CheckConstraint(
            "(opening_debit = 0 OR opening_credit = 0)",
            name="ck_balance_opening",
        ),
        CheckConstraint(
            "(closing_debit = 0 OR closing_credit = 0)",
            name="ck_balance_closing",
        ),
    )

    def __repr__(self) -> str:
        return f"<AccountBalance {self.account_id} P:{self.period_id}>"


class CarryTemplate(Base, UUIDPrimaryKeyMixin):
    """结转模板 — §2.8"""

    __tablename__ = "carry_templates"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rules: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=False, default=dict, comment="结转规则定义"
    )
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, default=0, nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Relationships ─────────────────────────────────────────
    carry_forwards: Mapped[List["CarryForward"]] = relationship(
        "CarryForward", back_populates="template"
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (Index("idx_carry_templates_sort", "sort_order"),)

    def __repr__(self) -> str:
        return f"<CarryTemplate {self.name}>"


class CarryForward(Base, UUIDPrimaryKeyMixin):
    """结转记录 — §2.7"""

    __tablename__ = "carry_forwards"

    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("periods.id"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("carry_templates.id"), nullable=False
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vouchers.id"), nullable=False
    )
    from_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    to_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Relationships ─────────────────────────────────────────
    period: Mapped["Period"] = relationship("Period", back_populates="carry_forwards")
    template: Mapped["CarryTemplate"] = relationship(
        "CarryTemplate", back_populates="carry_forwards"
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (Index("idx_carry_forwards_period", "period_id"),)

    def __repr__(self) -> str:
        return f"<CarryForward P:{self.period_id} amt={self.amount}>"
