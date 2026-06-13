"""initial — create all 14 tables with indexes from §2.15

Revision ID: 001
Revises:
Create Date: 2026-06-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── roles (§2.10) ─────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(50), unique=True, nullable=False),
        sa.Column("permissions", postgresql.JSONB, default={}),
    )

    # ── users (§2.10) ─────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), default=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── refresh_tokens (§2.11) ────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── accounts (§2.1) ───────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(20), unique=True, nullable=False, comment="科目编码 e.g. 1001"),
        sa.Column("name", sa.String(100), nullable=False, comment="科目名称"),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("level", sa.SmallInteger(), nullable=False, comment="Hierarchy level 1-4"),
        sa.Column("type", sa.String(20), nullable=False, comment="asset/liability/equity/revenue/expense"),
        sa.Column("dc_type", sa.String(1), nullable=False, comment="Balance direction: D=debit, C=credit"),
        sa.Column("is_cash", sa.Boolean(), default=False),
        sa.Column("aux_types", postgresql.JSONB, default=sa.text("'[]'::jsonb")),
        sa.Column("is_quantity", sa.Boolean(), default=False),
        sa.Column("quantity_unit", sa.String(20), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── departments / individuals / counterparties / projects (§2.5) ─
    for table_name in ["departments", "individuals", "counterparties", "projects"]:
        op.create_table(
            table_name,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
            sa.Column("code", sa.String(20), unique=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), default=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # ── periods (§2.6) ────────────────────────────────────
    op.create_table(
        "periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("month", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_period_year_month", "periods", ["year", "month"])

    # ── vouchers (§2.2) ───────────────────────────────────
    op.create_table(
        "vouchers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("voucher_no", sa.String(20), unique=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("periods.id"), nullable=False),
        sa.Column("attachments", sa.SmallInteger(), default=0),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("auditor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(50), server_default="manual"),
        sa.Column("ai_conversation", postgresql.JSONB, nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_voucher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vouchers.id"), nullable=True),
        sa.Column("reversal_type", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # §2.15 indexes
    op.create_index("idx_vouchers_period_status", "vouchers", ["period_id", "status"])
    op.create_index("idx_vouchers_date", "vouchers", ["date"])
    op.create_index("idx_vouchers_status_date", "vouchers", ["status", "date"])

    # ── voucher_entries (§2.3) ─────────────────────────────
    op.create_table(
        "voucher_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("voucher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vouchers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("row_number", sa.SmallInteger(), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("summary", sa.String(200), nullable=False),
        sa.Column("debit_amount", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("credit_amount", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("price", sa.Numeric(18, 4), nullable=True),
    )
    # XOR CHECK constraints
    op.create_check_constraint("ck_entries_xor_amount", "voucher_entries", "debit_amount = 0 OR credit_amount = 0")
    op.create_check_constraint("ck_entries_has_amount", "voucher_entries", "debit_amount > 0 OR credit_amount > 0")
    # §2.15 indexes
    op.create_index("idx_voucher_entries_account", "voucher_entries", ["account_id"])
    op.create_index("idx_voucher_entries_voucher", "voucher_entries", ["voucher_id"])
    op.create_index("idx_voucher_entries_account_voucher", "voucher_entries", ["account_id", "voucher_id"])

    # ── entry_auxiliaries (§2.4) ───────────────────────────
    op.create_table(
        "entry_auxiliaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("voucher_entries.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("aux_type", sa.String(20), nullable=False, comment="部门/个人/单位/项目"),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("individual_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("individuals.id"), nullable=True),
        sa.Column("counterparty_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("counterparties.id"), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
    )
    # Exactly-one-non-null CHECK
    op.create_check_constraint(
        "ck_entry_aux_exactly_one",
        "entry_auxiliaries",
        (
            "(CASE WHEN department_id IS NOT NULL THEN 1 ELSE 0 END +"
            " CASE WHEN individual_id IS NOT NULL THEN 1 ELSE 0 END +"
            " CASE WHEN counterparty_id IS NOT NULL THEN 1 ELSE 0 END +"
            " CASE WHEN project_id IS NOT NULL THEN 1 ELSE 0 END) = 1"
        ),
    )
    # §2.15 indexes
    op.create_index("idx_entry_aux_entry", "entry_auxiliaries", ["entry_id"])
    op.create_index("idx_entry_aux_dept", "entry_auxiliaries", ["department_id"])
    op.create_index("idx_entry_aux_individual", "entry_auxiliaries", ["individual_id"])
    op.create_index("idx_entry_aux_counterparty", "entry_auxiliaries", ["counterparty_id"])
    op.create_index("idx_entry_aux_project", "entry_auxiliaries", ["project_id"])

    # ── voucher_templates (§3.4) ───────────────────────────
    op.create_table(
        "voucher_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("entries", postgresql.JSONB, default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── account_balances (§2.9) ────────────────────────────
    op.create_table(
        "account_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("periods.id"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("opening_debit", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("opening_credit", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("current_debit", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("current_credit", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("closing_debit", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("closing_credit", sa.Numeric(18, 2), default=0, nullable=False),
    )
    op.create_unique_constraint("uq_balance_period_account", "account_balances", ["period_id", "account_id"])
    op.create_check_constraint("ck_balance_opening", "account_balances", "(opening_debit = 0 OR opening_credit = 0)")
    op.create_check_constraint("ck_balance_closing", "account_balances", "(closing_debit = 0 OR closing_credit = 0)")

    # ── carry_templates (§2.8) ─────────────────────────────
    op.create_table(
        "carry_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rules", postgresql.JSONB, default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), default=0, nullable=False),
        sa.Column("is_enabled", sa.Boolean(), default=True),
    )
    op.create_index("idx_carry_templates_sort", "carry_templates", ["sort_order"])

    # ── carry_forwards (§2.7) ──────────────────────────────
    op.create_table(
        "carry_forwards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("periods.id"), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("carry_templates.id"), nullable=False),
        sa.Column("voucher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vouchers.id"), nullable=False),
        sa.Column("from_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("to_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_carry_forwards_period", "carry_forwards", ["period_id"])

    # ── audit_logs (§2.12) ─────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("old_values", postgresql.JSONB, nullable=True),
        sa.Column("new_values", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_audit_logs_created", "audit_logs", [sa.text("created_at DESC")])
    op.create_index("idx_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("idx_audit_logs_user_created", "audit_logs", ["user_id", "created_at"])

    # ── cash_journals (§2.13) ──────────────────────────────
    op.create_table(
        "cash_journals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("periods.id"), nullable=False),
        sa.Column("voucher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vouchers.id"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("summary", sa.String(200), nullable=False),
        sa.Column("debit", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("credit", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("serial_no", sa.String(50), nullable=True),
        sa.Column("counterparty", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_cash_journals_account_date", "cash_journals", ["account_id", "date"])

    # ── bank_journals (§2.13) ──────────────────────────────
    op.create_table(
        "bank_journals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("periods.id"), nullable=False),
        sa.Column("voucher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vouchers.id"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("summary", sa.String(200), nullable=False),
        sa.Column("debit", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("credit", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("serial_no", sa.String(50), nullable=True),
        sa.Column("counterparty", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_bank_journals_account_date", "bank_journals", ["account_id", "date"])

    # ── fixed_assets (§2.14) ───────────────────────────────
    op.create_table(
        "fixed_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("purchase_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("salvage_value", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("useful_life_months", sa.Integer(), nullable=False),
        sa.Column("depreciation_method", sa.String(20), nullable=False, server_default="straight"),
        sa.Column("monthly_depreciation", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("accumulated_depreciation", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("net_value", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_use"),
        sa.Column("dept_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_fixed_assets_dept_status", "fixed_assets", ["dept_id", "status"])
    op.create_index("idx_fixed_assets_status", "fixed_assets", ["status"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_index("idx_fixed_assets_status", table_name="fixed_assets")
    op.drop_index("idx_fixed_assets_dept_status", table_name="fixed_assets")
    op.drop_table("fixed_assets")

    op.drop_index("idx_bank_journals_account_date", table_name="bank_journals")
    op.drop_table("bank_journals")

    op.drop_index("idx_cash_journals_account_date", table_name="cash_journals")
    op.drop_table("cash_journals")

    op.drop_index("idx_audit_logs_user_created", table_name="audit_logs")
    op.drop_index("idx_audit_logs_resource", table_name="audit_logs")
    op.drop_index("idx_audit_logs_created", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("idx_carry_forwards_period", table_name="carry_forwards")
    op.drop_table("carry_forwards")

    op.drop_index("idx_carry_templates_sort", table_name="carry_templates")
    op.drop_table("carry_templates")

    op.drop_table("account_balances")

    op.drop_table("voucher_templates")

    op.drop_index("idx_entry_aux_project", table_name="entry_auxiliaries")
    op.drop_index("idx_entry_aux_counterparty", table_name="entry_auxiliaries")
    op.drop_index("idx_entry_aux_individual", table_name="entry_auxiliaries")
    op.drop_index("idx_entry_aux_dept", table_name="entry_auxiliaries")
    op.drop_index("idx_entry_aux_entry", table_name="entry_auxiliaries")
    op.drop_table("entry_auxiliaries")

    op.drop_index("idx_voucher_entries_account_voucher", table_name="voucher_entries")
    op.drop_index("idx_voucher_entries_voucher", table_name="voucher_entries")
    op.drop_index("idx_voucher_entries_account", table_name="voucher_entries")
    op.drop_table("voucher_entries")

    op.drop_index("idx_vouchers_status_date", table_name="vouchers")
    op.drop_index("idx_vouchers_date", table_name="vouchers")
    op.drop_index("idx_vouchers_period_status", table_name="vouchers")
    op.drop_table("vouchers")

    op.drop_table("periods")

    for table_name in ["projects", "counterparties", "individuals", "departments"]:
        op.drop_table(table_name)

    op.drop_table("accounts")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("roles")
