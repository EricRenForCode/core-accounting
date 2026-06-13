"""Audit log model — §2.12"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """Audit trail — records all INSERT/UPDATE/DELETE operations — §2.12"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="INSERT/UPDATE/DELETE"
    )
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="voucher/account/period/..."
    )
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    old_values: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Pre-change values"
    )
    new_values: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Post-change values"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_audit_logs_created", "created_at"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
        Index("idx_audit_logs_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.resource_type}:{self.resource_id}>"
