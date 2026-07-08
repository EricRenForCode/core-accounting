"""004 — add original_documents table (原始凭证/票据附件)

Revision ID: 004
Revises: d3215670f9da
Create Date: 2026-07-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "d3215670f9da"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "original_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column(
            "document_type", sa.String(20), nullable=False, server_default="other"
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="uploaded"),
        sa.Column("issue_date", sa.Date, nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("counterparty_name", sa.String(200), nullable=True),
        sa.Column("invoice_no", sa.String(100), nullable=True),
        sa.Column("summary", sa.String(200), nullable=True),
        sa.Column("recognized_fields", postgresql.JSONB, nullable=True),
        sa.Column("recognition_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column(
            "voucher_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vouchers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploader_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_original_documents_status", "original_documents", ["status"]
    )
    op.create_index(
        "idx_original_documents_type", "original_documents", ["document_type"]
    )
    op.create_index(
        "idx_original_documents_voucher", "original_documents", ["voucher_id"]
    )
    op.create_index(
        "idx_original_documents_created", "original_documents", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_original_documents_created", table_name="original_documents")
    op.drop_index("idx_original_documents_voucher", table_name="original_documents")
    op.drop_index("idx_original_documents_type", table_name="original_documents")
    op.drop_index("idx_original_documents_status", table_name="original_documents")
    op.drop_table("original_documents")
