"""Seed script: create default roles, admin user, and basic chart of accounts.

Idempotent by section: roles, the admin user, and the chart of accounts are
each get-or-create, so re-running (or running against a DB that already has
some of them) safely fills in only what's missing — instead of skipping
everything the moment any role exists.
"""
import asyncio
import json
import os
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.security import hash_password

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://accounting:accounting@localhost:5432/core_accounting")

PERMISSIONS = [
    'voucher:create', 'voucher:edit:own', 'voucher:edit:any', 'voucher:delete:draft',
    'voucher:audit', 'voucher:unaudit', 'voucher:post', 'voucher:reverse',
    'account:read', 'account:manage', 'ledger:read', 'report:read', 'report:export',
    'period:close', 'period:reopen', 'aux:manage', 'cashier:use', 'assets:manage',
    'ai:use', 'admin:users', 'admin:roles', 'admin:backup', 'admin:audit-log',
]

DEFAULT_ACCOUNTS = [
    # Assets (1xxx)
    {"code": "1001", "name": "库存现金", "level": 1, "type": "asset", "dc_type": "D", "is_cash": True},
    {"code": "1002", "name": "银行存款", "level": 1, "type": "asset", "dc_type": "D", "is_cash": True},
    {"code": "1122", "name": "应收账款", "level": 1, "type": "asset", "dc_type": "D"},
    {"code": "1403", "name": "原材料", "level": 1, "type": "asset", "dc_type": "D"},
    {"code": "1405", "name": "库存商品", "level": 1, "type": "asset", "dc_type": "D"},
    {"code": "1601", "name": "固定资产", "level": 1, "type": "asset", "dc_type": "D"},
    # Liabilities (2xxx)
    {"code": "2001", "name": "短期借款", "level": 1, "type": "liability", "dc_type": "C"},
    {"code": "2202", "name": "应付账款", "level": 1, "type": "liability", "dc_type": "C"},
    {"code": "2221", "name": "应交税费", "level": 1, "type": "liability", "dc_type": "C"},
    # Equity (3xxx/4xxx)
    {"code": "4001", "name": "实收资本", "level": 1, "type": "equity", "dc_type": "C"},
    {"code": "4103", "name": "本年利润", "level": 1, "type": "equity", "dc_type": "C"},
    {"code": "4104", "name": "利润分配", "level": 1, "type": "equity", "dc_type": "C"},
    # Revenue (5xxx/6xxx)
    {"code": "6001", "name": "主营业务收入", "level": 1, "type": "revenue", "dc_type": "C"},
    {"code": "6051", "name": "其他业务收入", "level": 1, "type": "revenue", "dc_type": "C"},
    # Expenses (6xxx/7xxx)
    {"code": "6401", "name": "主营业务成本", "level": 1, "type": "expense", "dc_type": "D"},
    {"code": "6601", "name": "销售费用", "level": 1, "type": "expense", "dc_type": "D"},
    {"code": "6602", "name": "管理费用", "level": 1, "type": "expense", "dc_type": "D"},
    {"code": "6603", "name": "财务费用", "level": 1, "type": "expense", "dc_type": "D"},
]

async def get_or_create_role(db: AsyncSession, name: str, perms: dict) -> str:
    """Return the id of role `name`, creating it if it does not exist."""
    result = await db.execute(
        text("SELECT id FROM roles WHERE name = :name"), {"name": name}
    )
    existing = result.scalar()
    if existing is not None:
        return str(existing)
    rid = str(uuid4())
    await db.execute(
        text("INSERT INTO roles (id, name, permissions) VALUES (:id, :name, :perms::jsonb)"),
        {"id": rid, "name": name, "perms": json.dumps(perms)},
    )
    return rid


async def seed():
    engine = create_async_engine(DATABASE_URL)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as db:
        # ── Roles (get-or-create by unique name) ─────────────────────
        admin_perms = {p: True for p in PERMISSIONS}
        staff_perms = {p: p in [
            'voucher:create', 'voucher:edit:own', 'voucher:delete:draft',
            'account:read', 'ledger:read', 'report:read'
        ] for p in PERMISSIONS}
        manager_perms = {p: p not in ['admin:users', 'admin:roles', 'admin:backup'] for p in PERMISSIONS}

        admin_role_id = await get_or_create_role(db, "admin", admin_perms)
        await get_or_create_role(db, "finance_staff", staff_perms)
        await get_or_create_role(db, "finance_manager", manager_perms)

        # ── Admin user (get-or-create by unique username) ────────────
        result = await db.execute(
            text("SELECT id FROM users WHERE username = :u"), {"u": "admin"}
        )
        admin_created = False
        if result.scalar() is None:
            await db.execute(
                text("INSERT INTO users (id, username, password_hash, display_name, role_id, is_enabled) VALUES (:id, :username, :ph, :dn, :rid, :enabled)"),
                {"id": str(uuid4()), "username": "admin", "ph": hash_password("admin123"),
                 "dn": "系统管理员", "rid": admin_role_id, "enabled": True},
            )
            admin_created = True

        # ── Chart of accounts (get-or-create by unique code) ─────────
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        accounts_created = 0
        for acct in DEFAULT_ACCOUNTS:
            result = await db.execute(
                text(
                    "INSERT INTO accounts (id, code, name, level, type, dc_type, is_cash, is_enabled, created_at, updated_at) "
                    "VALUES (:id, :code, :name, :level, :type, :dc_type, :is_cash, :enabled, :now, :now) "
                    "ON CONFLICT (code) DO NOTHING"
                ),
                {
                    "id": str(uuid4()),
                    "code": acct["code"],
                    "name": acct["name"],
                    "level": acct["level"],
                    "type": acct["type"],
                    "dc_type": acct["dc_type"],
                    "is_cash": acct.get("is_cash", False),
                    "enabled": True,
                    "now": now,
                },
            )
            accounts_created += result.rowcount or 0

        await db.commit()
        admin_note = "admin user (admin/admin123)" if admin_created else "admin user already existed (password unchanged)"
        print(
            f"Seed done: roles ensured, {admin_note}, "
            f"{accounts_created}/{len(DEFAULT_ACCOUNTS)} accounts created "
            f"({len(DEFAULT_ACCOUNTS) - accounts_created} already present)."
        )

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed())
