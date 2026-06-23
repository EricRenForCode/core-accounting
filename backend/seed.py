"""Seed script: create default roles, admin user, and basic chart of accounts."""
import asyncio
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

async def seed():
    engine = create_async_engine(DATABASE_URL)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as db:
        # Check if already seeded
        result = await db.execute(text("SELECT count(*) FROM roles"))
        if result.scalar() > 0:
            print("Database already seeded, skipping.")
            return

        # Create roles
        admin_role_id = str(uuid4())
        staff_role_id = str(uuid4())
        manager_role_id = str(uuid4())

        admin_perms = {p: True for p in PERMISSIONS}
        staff_perms = {p: p in [
            'voucher:create', 'voucher:edit:own', 'voucher:delete:draft',
            'account:read', 'ledger:read', 'report:read'
        ] for p in PERMISSIONS}
        manager_perms = {p: p not in ['admin:users', 'admin:roles', 'admin:backup'] for p in PERMISSIONS}

        for rid, name, perms in [
            (admin_role_id, "admin", admin_perms),
            (staff_role_id, "finance_staff", staff_perms),
            (manager_role_id, "finance_manager", manager_perms),
        ]:
            await db.execute(
                text("INSERT INTO roles (id, name, permissions) VALUES (:id, :name, :perms::jsonb)"),
                {"id": rid, "name": name, "perms": str(perms).replace("'", '"')},
            )

        # Create admin user (password: admin123)
        password_hash = hash_password("admin123")
        admin_id = str(uuid4())
        await db.execute(
            text("INSERT INTO users (id, username, password_hash, display_name, role_id, is_enabled) VALUES (:id, :username, :ph, :dn, :rid, :enabled)"),
            {"id": admin_id, "username": "admin", "ph": password_hash, "dn": "系统管理员", "rid": admin_role_id, "enabled": True},
        )

        # Create chart of accounts
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for acct in DEFAULT_ACCOUNTS:
            await db.execute(
                text("INSERT INTO accounts (id, code, name, level, type, dc_type, is_cash, is_enabled, created_at, updated_at) VALUES (:id, :code, :name, :level, :type, :dc_type, :is_cash, :enabled, :now, :now)"),
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

        await db.commit()
        print(f"Seeded: 3 roles, 1 admin user (admin/admin123), {len(DEFAULT_ACCOUNTS)} accounts")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed())
