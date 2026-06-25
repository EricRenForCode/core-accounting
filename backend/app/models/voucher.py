"""Voucher, VoucherEntry, and VoucherTemplate models — §2.2, §2.3, §3.4"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.user import User
    from app.models.period import Period
    from app.models.auxiliary import EntryAuxiliary


class Voucher(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Accounting voucher (凭证) — §2.2."""

    __tablename__ = "vouchers"

    voucher_no: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, comment="凭证号 JZ-2026-06-001"
    )
    date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="凭证日期"
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("periods.id"), nullable=False
    )
    attachments: Mapped[int] = mapped_column(
        SmallInteger, default=0, comment="附单据数"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        comment="draft/audited/posted/reversed",
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    auditor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="记账时间"
    )
    source: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        comment="manual/template/ai/import",
    )
    ai_conversation: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="AI生成对话记录"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, comment="软删除标记"
    )
    reversed_voucher_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vouchers.id"),
        nullable=True,
        comment="冲销来源凭证",
    )
    reversal_type: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="full/partial"
    )

    # ── Relationships ─────────────────────────────────────────
    period: Mapped["Period"] = relationship("Period", back_populates="vouchers")
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[creator_id], back_populates="created_vouchers"
    )
    auditor: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[auditor_id], back_populates="audited_vouchers"
    )
    entries: Mapped[List["VoucherEntry"]] = relationship(
        "VoucherEntry",
        back_populates="voucher",
        cascade="all, delete-orphan",
        order_by="VoucherEntry.row_number",
    )
    reversed_voucher: Mapped[Optional["Voucher"]] = relationship(
        "Voucher",
        remote_side="Voucher.id",
        back_populates="reversals",
    )
    reversals: Mapped[List["Voucher"]] = relationship(
        "Voucher", back_populates="reversed_voucher"
    )

    # ── Constraints / Indexes ─────────────────────────────────
    __table_args__ = (
        Index("idx_vouchers_period_status", "period_id", "status"),
        Index("idx_vouchers_date", "date"),
        Index("idx_vouchers_status_date", "status", "date"),
        Index("idx_vouchers_voucher_no", "voucher_no"),
    )

    def __repr__(self) -> str:
        return f"<Voucher {self.voucher_no} [{self.status}]>"


class VoucherEntry(Base, UUIDPrimaryKeyMixin):
    """Voucher entry line item (凭证分录) — §2.3."""

    __tablename__ = "voucher_entries"

    voucher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vouchers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="分录行号"
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="摘要"
    )
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, nullable=False, comment="借方金额"
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, nullable=False, comment="贷方金额"
    )
    quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True, comment="数量"
    )
    price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 4), nullable=True, comment="单价"
    )

    # ── Relationships ─────────────────────────────────────────
    voucher: Mapped["Voucher"] = relationship("Voucher", back_populates="entries")
    account: Mapped["Account"] = relationship("Account", back_populates="entries")
    auxiliaries: Mapped[List["EntryAuxiliary"]] = relationship(
        "EntryAuxiliary",
        back_populates="entry",
        cascade="all, delete-orphan",
    )

    # ── Constraints / Indexes ─────────────────────────────────
    __table_args__ = (
        CheckConstraint(
            "debit_amount = 0 OR credit_amount = 0",
            name="ck_entries_xor_amount",
        ),
        CheckConstraint(
            "debit_amount > 0 OR credit_amount > 0",
            name="ck_entries_has_amount",
        ),
        Index("idx_voucher_entries_account", "account_id"),
        Index("idx_voucher_entries_voucher", "voucher_id"),
        Index("idx_voucher_entries_account_voucher", "account_id", "voucher_id"),
    )

    @validates("debit_amount", "credit_amount")
    def validate_xor(self, key: str, value: Decimal) -> Decimal:
        """XOR validator: exactly one of debit/credit must be > 0."""
        return value

    def __repr__(self) -> str:
        amt = (
            f"D:{self.debit_amount}"
            if self.debit_amount
            else f"C:{self.credit_amount}"
        )
        return f"<VoucherEntry #{self.row_number} {amt} {self.summary}>"


class VoucherTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Voucher template (凭证模板) — §3.4."""

    __tablename__ = "voucher_templates"

    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="模板名称"
    )
    description: Mapped[Optional[str]] = mapped_column(
        nullable=True, comment="模板说明"
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="模板分类"
    )
    entries: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="预置分录定义 [{account_id, summary, dc_side, auxiliaries}]",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True
    )

    def __repr__(self) -> str:
        return f"<VoucherTemplate {self.name}>"
