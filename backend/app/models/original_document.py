"""OriginalDocument model — 原始凭证/票据附件 (source documents).

Workflow: uploaded → recognized/needs_review → voucher_created → archived.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.voucher import Voucher

DOCUMENT_TYPES = (
    "invoice",
    "bank_receipt",
    "reimbursement",
    "contract",
    "payroll",
    "other",
)

DOCUMENT_STATUSES = (
    "uploaded",
    "recognized",
    "needs_review",
    "voucher_created",
    "archived",
)


class OriginalDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Uploaded source document (原始凭证) with recognized fields."""

    __tablename__ = "original_documents"

    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="原始文件名（已清洗）"
    )
    storage_key: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="存储相对路径/key"
    )
    content_type: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="MIME 类型"
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="文件大小（字节）"
    )
    document_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="other",
        comment="invoice/bank_receipt/reimbursement/contract/payroll/other",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="uploaded",
        comment="uploaded/recognized/needs_review/voucher_created/archived",
    )
    issue_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="票据日期"
    )
    amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True, comment="金额（不含税）"
    )
    tax_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True, comment="税额"
    )
    total_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True, comment="价税合计"
    )
    counterparty_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="对方单位"
    )
    invoice_no: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="发票号码"
    )
    summary: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="摘要"
    )
    recognized_fields: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="OCR/AI 识别结果（含 suggested_entries）"
    )
    recognition_confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3), nullable=True, comment="识别置信度 0-1"
    )
    voucher_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vouchers.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联记账凭证",
    )
    uploader_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────
    voucher: Mapped[Optional["Voucher"]] = relationship("Voucher")
    uploader: Mapped["User"] = relationship("User")

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("idx_original_documents_status", "status"),
        Index("idx_original_documents_type", "document_type"),
        Index("idx_original_documents_voucher", "voucher_id"),
        Index("idx_original_documents_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<OriginalDocument {self.file_name} [{self.status}]>"
