"""002 — add system_params table

Revision ID: 002
Revises: 001
Create Date: 2026-06-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_params",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(50), unique=True, nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Seed default parameters
    op.execute(
        sa.text(
            """
            INSERT INTO system_params (id, key, value) VALUES
            (gen_random_uuid(), 'company_name', ''),
            (gen_random_uuid(), 'base_currency', 'CNY'),
            (gen_random_uuid(), 'accounting_standard', '企业会计准则'),
            (gen_random_uuid(), 'voucher_no_prefix', 'JZ'),
            (gen_random_uuid(), 'default_depreciation_method', 'straight')
            """
        )
    )


def downgrade() -> None:
    op.drop_table("system_params")
