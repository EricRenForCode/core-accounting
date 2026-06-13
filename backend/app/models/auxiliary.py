"""Auxiliary核算 models — §2.4, §2.5

Four archive tables (departments, individuals, counterparties, projects)
plus the entry_auxiliaries join table with exactly-one-non-null CHECK.
"""

import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.voucher import VoucherEntry


# ── Auxiliary Archive Tables (§2.5) ────────────────────────────
# All four share the same structure: id, code, name, is_enabled, created_at.


class Department(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """部门档案 — §2.5"""

    __tablename__ = "departments"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    entry_auxiliaries: Mapped[List["EntryAuxiliary"]] = relationship(
        "EntryAuxiliary", back_populates="department"
    )

    def __repr__(self) -> str:
        return f"<Department {self.code} {self.name}>"


class Individual(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """个人档案 — §2.5"""

    __tablename__ = "individuals"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    entry_auxiliaries: Mapped[List["EntryAuxiliary"]] = relationship(
        "EntryAuxiliary", back_populates="individual"
    )

    def __repr__(self) -> str:
        return f"<Individual {self.code} {self.name}>"


class Counterparty(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """往来单位档案 — §2.5"""

    __tablename__ = "counterparties"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    entry_auxiliaries: Mapped[List["EntryAuxiliary"]] = relationship(
        "EntryAuxiliary", back_populates="counterparty"
    )

    def __repr__(self) -> str:
        return f"<Counterparty {self.code} {self.name}>"


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """项目档案 — §2.5"""

    __tablename__ = "projects"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    entry_auxiliaries: Mapped[List["EntryAuxiliary"]] = relationship(
        "EntryAuxiliary", back_populates="project"
    )

    def __repr__(self) -> str:
        return f"<Project {self.code} {self.name}>"


# ── Entry Auxiliary Join Table (§2.4) ──────────────────────────


class EntryAuxiliary(Base, UUIDPrimaryKeyMixin):
    """Link between voucher_entries and auxiliary核算 entities — §2.4."""

    __tablename__ = "entry_auxiliaries"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("voucher_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    aux_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="部门/个人/单位/项目",
    )

    # Four nullable FKs — exactly one must be non-null (CHECK below)
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    individual_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("individuals.id"), nullable=True
    )
    counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparties.id"), nullable=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────
    entry: Mapped["VoucherEntry"] = relationship(
        "VoucherEntry", back_populates="auxiliaries"
    )
    department: Mapped[Optional["Department"]] = relationship(
        "Department", back_populates="entry_auxiliaries"
    )
    individual: Mapped[Optional["Individual"]] = relationship(
        "Individual", back_populates="entry_auxiliaries"
    )
    counterparty: Mapped[Optional["Counterparty"]] = relationship(
        "Counterparty", back_populates="entry_auxiliaries"
    )
    project: Mapped[Optional["Project"]] = relationship(
        "Project", back_populates="entry_auxiliaries"
    )

    # ── Constraints / Indexes ─────────────────────────────────
    __table_args__ = (
        CheckConstraint(
            (
                "(CASE WHEN department_id IS NOT NULL THEN 1 ELSE 0 END +"
                " CASE WHEN individual_id IS NOT NULL THEN 1 ELSE 0 END +"
                " CASE WHEN counterparty_id IS NOT NULL THEN 1 ELSE 0 END +"
                " CASE WHEN project_id IS NOT NULL THEN 1 ELSE 0 END) = 1"
            ),
            name="ck_entry_aux_exactly_one",
        ),
        Index("idx_entry_aux_entry", "entry_id"),
        Index("idx_entry_aux_dept", "department_id"),
        Index("idx_entry_aux_individual", "individual_id"),
        Index("idx_entry_aux_counterparty", "counterparty_id"),
        Index("idx_entry_aux_project", "project_id"),
    )

    def __repr__(self) -> str:
        return f"<EntryAuxiliary {self.aux_type} entry={self.entry_id}>"
