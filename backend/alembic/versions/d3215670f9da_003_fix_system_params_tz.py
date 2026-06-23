"""003 — fix system_params updated_at timezone

Revision ID: d3215670f9da
Revises: 002
Create Date: 2026-06-19 14:53:11.429109
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd3215670f9da'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'system_params', 'updated_at',
        existing_type=postgresql.TIMESTAMP(timezone=False),
        type_=postgresql.TIMESTAMP(timezone=True),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'system_params', 'updated_at',
        existing_type=postgresql.TIMESTAMP(timezone=True),
        type_=postgresql.TIMESTAMP(timezone=False),
        existing_nullable=False,
    )
