"""Models package — imports all ORM models for Alembic auto-detection."""

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.account import Account
from app.models.voucher import Voucher, VoucherEntry, VoucherTemplate
from app.models.auxiliary import (
    Department,
    Individual,
    Counterparty,
    Project,
    EntryAuxiliary,
)
from app.models.period import Period, AccountBalance, CarryTemplate, CarryForward
from app.models.user import User, Role, RefreshToken
from app.models.audit import AuditLog
from app.models.cashier import CashJournal, BankJournal
from app.models.asset import FixedAsset

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    # Account
    "Account",
    # Voucher
    "Voucher",
    "VoucherEntry",
    "VoucherTemplate",
    # Auxiliary
    "Department",
    "Individual",
    "Counterparty",
    "Project",
    "EntryAuxiliary",
    # Period
    "Period",
    "AccountBalance",
    "CarryTemplate",
    "CarryForward",
    # User
    "User",
    "Role",
    "RefreshToken",
    # Audit
    "AuditLog",
    # Cashier
    "CashJournal",
    "BankJournal",
    # Asset
    "FixedAsset",
]
