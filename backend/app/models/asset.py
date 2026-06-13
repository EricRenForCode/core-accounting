"""Fixed Asset model — §2.14"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class FixedAsset(Base, UUIDPrimaryKeyMixin):
    """固定资产卡片 — §2.14"""

    __tablename__ = "fixed_assets"

    code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, comment="资产编码"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="资产名称"
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="资产类别"
    )
    purchase_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="购置日期"
    )
    purchase_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, comment="原值"
    )
    salvage_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, nullable=False, comment="残值"
    )
    useful_life_months: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="使用年限(月)"
    )
    depreciation_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="straight",
        comment="straight/double_declining/sum_of_years",
    )
    monthly_depreciation: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, nullable=False, comment="月折旧额"
    )
    accumulated_depreciation: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, nullable=False, comment="累计折旧"
    )
    net_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=0, nullable=False, comment="净值"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="in_use",
        comment="in_use/disposed/cleared",
    )
    dept_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id"),
        nullable=True,
        comment="使用部门",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_fixed_assets_dept_status", "dept_id", "status"),
        Index("idx_fixed_assets_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<FixedAsset {self.code} {self.name}>"
