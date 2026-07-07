"""Test fixtures for Core Accounting backend tests.

Provides:
- Async SQLite in-memory engine + session
- FastAPI TestClient with overridden dependencies
- Authenticated test user + auth headers
- Domain fixtures (periods, accounts, vouchers)

PostgreSQL types (JSONB, INET, UUID) are compiled to SQLite equivalents.
SQLite limitations: no SELECT FOR UPDATE support (post/reverse tests xfail).
"""

import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator, Optional

# Disable the Redis cache layer for the entire suite BEFORE app modules
# import — a live local Redis would otherwise leak cached responses
# (account trees, trial balances) across tests with fresh in-memory DBs.
os.environ["CACHE_ENABLED"] = "false"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB, INET, UUID as PG_UUID


# ── PostgreSQL → SQLite Type Compilation --------------------

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(INET, "sqlite")
def _compile_inet_sqlite(type_, compiler, **kw):
    return "VARCHAR(45)"

@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"

# UUID bind/result processing for SQLite
_orig_uuid_rp = PG_UUID.result_processor
_orig_uuid_bp = PG_UUID.bind_processor

def _sqlite_uuid_result_processor(dialect, coltype):
    if dialect.name == "sqlite":
        def process(value):
            if value is None: return None
            if isinstance(value, uuid.UUID): return value
            return uuid.UUID(value) if isinstance(value, str) else value
        return process
    return _orig_uuid_rp(dialect, coltype)

def _sqlite_uuid_bind_processor(dialect):
    if dialect.name == "sqlite":
        def process(value):
            if value is None: return None
            return str(value)
        return process
    return _orig_uuid_bp(dialect)

PG_UUID.result_processor = staticmethod(_sqlite_uuid_result_processor)
PG_UUID.bind_processor = staticmethod(_sqlite_uuid_bind_processor)


# ── Imports ──────────────────────────────────────────────────

from app.core.database import get_ai_readonly_db, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.base import Base
from app.models.account import Account
from app.models.user import Role, User
from app.models.period import AccountBalance, CarryForward, CarryTemplate, Period
from app.models.voucher import Voucher, VoucherEntry, VoucherTemplate
from app.models.auxiliary import Department, Individual, Counterparty, Project, EntryAuxiliary
from app.models.asset import FixedAsset
from app.models.cashier import CashJournal, BankJournal
from app.models.audit import AuditLog
from app.models.system_param import SystemParam


# ── Engine ───────────────────────────────────────────────────

@pytest_asyncio.fixture
async def engine():
    # Fresh in-memory DB per test for isolation. StaticPool keeps a single
    # shared connection so seed sessions and API request sessions see the
    # same in-memory database.
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


# ── Session ──────────────────────────────────────────────────

@pytest_asyncio.fixture
async def async_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Session for seeding fixture data. Commits so data visible to API."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.commit()


# ── Client ───────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client — each request gets a fresh session (matches production get_db)."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        # Match production get_db semantics: commit on success, rollback on error.
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_ai_readonly_db():
        # Same error semantics as get_db: a failed AI query must not poison
        # the shared in-memory connection for subsequent requests.
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ai_readonly_db] = override_get_ai_readonly_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Seed Helpers ──────────────────────────────────────────────

async def _create_test_role(db: AsyncSession, name: str = "finance_manager") -> Role:
    from sqlalchemy import select
    result = await db.execute(select(Role).where(Role.name == name))
    role = result.scalar_one_or_none()
    if role: return role
    perms = ["voucher:create","voucher:edit:own","voucher:edit:any","voucher:delete:draft",
             "voucher:audit","voucher:unaudit","voucher:post","voucher:reverse",
             "account:read","account:manage","ledger:read","report:read","report:export",
             "period:close","period:reopen","aux:manage","cashier:use","assets:manage",
             "ai:use","admin:users","admin:roles","admin:backup","admin:audit-log"]
    role = Role(id=uuid.uuid4(), name=name, permissions={p: True for p in perms})
    # Commit (not just flush): seeded data must survive mid-test rollbacks —
    # error-path requests roll back the shared StaticPool connection, and a
    # flush-only seed would be silently wiped (manifests as 401s mid-test).
    db.add(role); await db.commit(); return role

async def _create_test_user(db: AsyncSession, username: str = "testuser",
                            display_name: str = "Test User", role_name: str = "finance_manager") -> User:
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user: return user
    role = await _create_test_role(db, role_name)
    user = User(id=uuid.uuid4(), username=username, password_hash=hash_password("testpass123"),
                display_name=display_name, role_id=role.id, is_enabled=True)
    db.add(user); await db.commit(); return user

async def _create_test_period(db: AsyncSession, year: int = 2026, month: int = 6,
                              status: str = "open") -> Period:
    from sqlalchemy import select
    result = await db.execute(select(Period).where(Period.year == year, Period.month == month))
    period = result.scalar_one_or_none()
    if period: return period
    period = Period(id=uuid.uuid4(), year=year, month=month, status=status)
    db.add(period); await db.commit(); return period

async def _create_test_accounts(db: AsyncSession) -> tuple[Account, Account, Account]:
    from sqlalchemy import select
    result = await db.execute(select(Account).where(Account.code == "1001"))
    cash = result.scalar_one_or_none()
    if not cash:
        cash = Account(id=uuid.uuid4(), code="1001", name="库存现金", level=1, type="asset", dc_type="D", is_cash=True, is_enabled=True)
        db.add(cash)
    result = await db.execute(select(Account).where(Account.code == "6602"))
    expense = result.scalar_one_or_none()
    if not expense:
        expense = Account(id=uuid.uuid4(), code="6602", name="管理费用-差旅费", level=2, type="expense", dc_type="D", is_enabled=True)
        db.add(expense)
    result = await db.execute(select(Account).where(Account.code == "2202"))
    liability = result.scalar_one_or_none()
    if not liability:
        liability = Account(id=uuid.uuid4(), code="2202", name="应付账款", level=1, type="liability", dc_type="C", is_enabled=True)
        db.add(liability)
    await db.commit()
    return cash, expense, liability

async def _create_voucher(db: AsyncSession, user: User, period: Period, cash: Account,
                          expense: Account, status: str = "draft", amount: Decimal = Decimal("5000.00"),
                          auditor: Optional[User] = None, posted: bool = False) -> Voucher:
    import random
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select as sa_select
    suffix = status[:2].upper() + str(random.randint(100, 999))
    voucher_no = f"JZ-{period.year}-{period.month:02d}-{suffix}"
    voucher = Voucher(id=uuid.uuid4(), voucher_no=voucher_no, date=date(period.year, period.month, 15),
                      period_id=period.id, status=status, creator_id=user.id,
                      auditor_id=auditor.id if auditor else None, source="manual")
    if posted: voucher.posted_at = datetime.now(timezone.utc)
    db.add(voucher); await db.flush()
    e1 = VoucherEntry(id=uuid.uuid4(), voucher_id=voucher.id, row_number=1, account_id=expense.id,
                      summary="支付差旅费", debit_amount=amount, credit_amount=Decimal("0"))
    e2 = VoucherEntry(id=uuid.uuid4(), voucher_id=voucher.id, row_number=2, account_id=cash.id,
                      summary="支付差旅费", debit_amount=Decimal("0"), credit_amount=amount)
    db.add_all([e1, e2]); await db.commit()
    result = await db.execute(sa_select(Voucher).options(
        selectinload(Voucher.entries).selectinload(VoucherEntry.account),
        selectinload(Voucher.entries).selectinload(VoucherEntry.auxiliaries),
    ).where(Voucher.id == voucher.id))
    return result.unique().scalar_one()


# ── User / Auth Fixtures ──────────────────────────────────────

@pytest_asyncio.fixture
async def test_role(async_session: AsyncSession) -> Role:
    return await _create_test_role(async_session)

@pytest_asyncio.fixture
async def test_user(async_session: AsyncSession) -> User:
    return await _create_test_user(async_session)

@pytest_asyncio.fixture
async def test_user2(async_session: AsyncSession) -> User:
    return await _create_test_user(async_session, username="testuser2", display_name="Test User 2")

@pytest_asyncio.fixture
async def auth_headers(async_session: AsyncSession) -> dict:
    user = await _create_test_user(async_session)
    role = await _create_test_role(async_session)
    perms = list((role.permissions or {}).keys())
    token = create_access_token(user_id=str(user.id), username=user.username, role=role.name, permissions=perms)
    return {"Authorization": f"Bearer {token}"}

@pytest_asyncio.fixture
async def auth_headers_user2(async_session: AsyncSession) -> dict:
    user = await _create_test_user(async_session, username="testuser2", display_name="Test User 2")
    role = await _create_test_role(async_session)
    perms = list((role.permissions or {}).keys())
    token = create_access_token(user_id=str(user.id), username=user.username, role=role.name, permissions=perms)
    return {"Authorization": f"Bearer {token}"}


# ── Domain Fixtures ───────────────────────────────────────────

@pytest_asyncio.fixture
async def test_period(async_session: AsyncSession) -> Period:
    return await _create_test_period(async_session)

@pytest_asyncio.fixture
async def test_accounts(async_session: AsyncSession) -> tuple[Account, Account, Account]:
    return await _create_test_accounts(async_session)

@pytest_asyncio.fixture
async def test_cash_account(async_session: AsyncSession) -> Account:
    cash, _, _ = await _create_test_accounts(async_session); return cash

@pytest_asyncio.fixture
async def test_expense_account(async_session: AsyncSession) -> Account:
    _, expense, _ = await _create_test_accounts(async_session); return expense

@pytest_asyncio.fixture
async def test_liability_account(async_session: AsyncSession) -> Account:
    _, _, liability = await _create_test_accounts(async_session); return liability

@pytest_asyncio.fixture
async def test_quantity_account(async_session: AsyncSession) -> Account:
    """An inventory account with quantity accounting enabled (for 数量金额账)."""
    from sqlalchemy import select
    result = await async_session.execute(select(Account).where(Account.code == "1405"))
    acct = result.scalar_one_or_none()
    if not acct:
        acct = Account(id=uuid.uuid4(), code="1405", name="库存商品", level=1,
                       type="asset", dc_type="D", is_quantity=True, is_enabled=True)
        async_session.add(acct); await async_session.flush()
    return acct

@pytest_asyncio.fixture
async def draft_voucher(async_session: AsyncSession) -> Voucher:
    user = await _create_test_user(async_session)
    period = await _create_test_period(async_session)
    cash, expense, _ = await _create_test_accounts(async_session)
    return await _create_voucher(async_session, user, period, cash, expense, "draft")

@pytest_asyncio.fixture
async def audited_voucher(async_session: AsyncSession) -> Voucher:
    user = await _create_test_user(async_session)
    user2 = await _create_test_user(async_session, username="testuser2", display_name="Test User 2")
    period = await _create_test_period(async_session)
    cash, expense, _ = await _create_test_accounts(async_session)
    return await _create_voucher(async_session, user, period, cash, expense, "audited", auditor=user2)

@pytest_asyncio.fixture
async def posted_voucher(async_session: AsyncSession) -> Voucher:
    user = await _create_test_user(async_session)
    user2 = await _create_test_user(async_session, username="testuser2", display_name="Test User 2")
    period = await _create_test_period(async_session)
    cash, expense, _ = await _create_test_accounts(async_session)
    return await _create_voucher(async_session, user, period, cash, expense, "posted", auditor=user2, posted=True)
