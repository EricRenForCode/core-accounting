"""Cash and Bank Journal models — §2.13"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class CashJournal(Base, UUIDPrimaryKeyMixin):
    """现金日记账 — §2.13"""

    __tablename__ = "cash_journals"

    date: Mapped[date] = mapped_column(Date, nullable=False)
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("periods.id"), nullable=False
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vouchers.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    summary: Mapped[str] = mapped_column(String(200), nullable=False)
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    serial_no: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="支票号/凭证号"
    )
    counterparty: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="对方单位/摘要"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_cash_journals_account_date", "account_id", "date"),
    )

    def __repr__(self) -> str:
        return f"<CashJournal {self.date} {self.summary}>"


class BankJournal(Base, UUIDPrimaryKeyMixin):
    """银行日记账 — §2.13"""

    __tablename__ = "bank_journals"

    date: Mapped[date] = mapped_column(Date, nullable=False)
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("periods.id"), nullable=False
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vouchers.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    summary: Mapped[str] = mapped_column(String(200), nullable=False)
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    serial_no: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="支票号/凭证号"
    )
    counterparty: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_bank_journals_account_date", "account_id", "date"),
    )

    def __repr__(self) -> str:
        return f"<BankJournal {self.date} {self.summary}>"
