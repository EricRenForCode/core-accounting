"""Seed realistic demo company data for MVP presentations.

This script assumes `seed.py` has already created the default roles, admin user,
and base chart of accounts. It imports a half-year operating dataset for a
small business with roughly RMB 100M annualized revenue.

The import is intentionally one-shot and idempotent: if any voucher with
source='demo_seed' exists, the script exits without creating duplicates.
"""

import asyncio
import uuid
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.core.security import hash_password
from app.models.account import Account
from app.models.asset import FixedAsset
from app.models.auxiliary import Counterparty, Department, EntryAuxiliary, Individual, Project
from app.models.cashier import BankJournal, CashJournal
from app.models.period import AccountBalance, Period
from app.models.user import Role, User
from app.models.voucher import Voucher, VoucherEntry


DEMO_SOURCE = "demo_seed"
DATABASE_URL = Settings().DATABASE_URL
MONEY = Decimal("0.01")


def d(value: str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(MONEY)


@dataclass(frozen=True)
class MonthPlan:
    month: int
    revenue_a: Decimal
    revenue_b: Decimal
    purchase: Decimal
    cogs: Decimal
    supplier_payment: Decimal
    customer_receipt: Decimal
    payroll: Decimal
    marketing: Decimal
    travel: Decimal
    office: Decimal
    rent: Decimal
    interest: Decimal
    depreciation: Decimal
    tax_surcharge: Decimal
    tax_payment: Decimal


MONTHS = [
    MonthPlan(1, d("4200000"), d("3000000"), d("5000000"), d("4300000"), d("3600000"), d("7000000"), d("610000"), d("180000"), d("42000"), d("52000"), d("98000"), d("31000"), d("88000"), d("41000"), d("420000")),
    MonthPlan(2, d("4500000"), d("3300000"), d("5200000"), d("4550000"), d("4100000"), d("7600000"), d("620000"), d("220000"), d("38000"), d("46000"), d("98000"), d("32000"), d("88000"), d("43000"), d("470000")),
    MonthPlan(3, d("5100000"), d("3600000"), d("5800000"), d("5050000"), d("4500000"), d("8300000"), d("630000"), d("260000"), d("51000"), d("58000"), d("98000"), d("33000"), d("90000"), d("48000"), d("520000")),
    MonthPlan(4, d("5400000"), d("3800000"), d("6000000"), d("5350000"), d("5200000"), d("8700000"), d("650000"), d("310000"), d("56000"), d("62000"), d("100000"), d("34000"), d("90000"), d("52000"), d("570000")),
    MonthPlan(5, d("5600000"), d("3900000"), d("6300000"), d("5600000"), d("5400000"), d("9100000"), d("670000"), d("360000"), d("64000"), d("69000"), d("100000"), d("35000"), d("92000"), d("55000"), d("620000")),
    MonthPlan(6, d("5900000"), d("4100000"), d("6700000"), d("5950000"), d("5800000"), d("9700000"), d("690000"), d("420000"), d("72000"), d("76000"), d("102000"), d("36000"), d("92000"), d("61000"), d("680000")),
]


DEPARTMENTS = [
    ("D001", "总经办"),
    ("D002", "财务部"),
    ("D003", "销售部"),
    ("D004", "交付实施部"),
    ("D005", "运营支持部"),
    ("D006", "研发与产品部"),
]

EMPLOYEES = [
    ("E001", "张晨"), ("E002", "李雯"), ("E003", "王磊"), ("E004", "赵敏"), ("E005", "陈昊"),
    ("E006", "刘洋"), ("E007", "杨帆"), ("E008", "周倩"), ("E009", "吴迪"), ("E010", "孙婷"),
    ("E011", "黄琪"), ("E012", "徐宁"), ("E013", "何佳"), ("E014", "郭瑞"), ("E015", "林悦"),
    ("E016", "罗明"), ("E017", "宋洁"), ("E018", "郑凯"), ("E019", "唐雨"), ("E020", "马琳"),
    ("E021", "胡斌"), ("E022", "丁蕾"), ("E023", "谢航"), ("E024", "姚瑶"), ("E025", "朱远"),
]

COUNTERPARTIES = [
    ("C001", "北京星河智能科技有限公司"),
    ("C002", "上海云链商业有限公司"),
    ("C003", "深圳微澜信息技术有限公司"),
    ("C004", "杭州知行数据服务有限公司"),
    ("S001", "北京华采电子有限公司"),
    ("S002", "苏州启明设备有限公司"),
    ("S003", "上海凌越软件服务有限公司"),
    ("S004", "广州远航物流有限公司"),
    ("S005", "北京中环物业管理有限公司"),
    ("S006", "招商银行北京分行"),
]

PROJECTS = [
    ("P001", "华北企业数字化项目"),
    ("P002", "华东渠道交付项目"),
    ("P003", "存量客户续费项目"),
    ("P004", "新产品试点项目"),
]


async def get_one(db: AsyncSession, model, **where):
    stmt = select(model)
    for key, value in where.items():
        stmt = stmt.where(getattr(model, key) == value)
    return (await db.execute(stmt)).scalar_one_or_none()


async def ensure_archive(db: AsyncSession, model, code: str, name: str):
    existing = await get_one(db, model, code=code)
    if existing:
        return existing
    row = model(id=uuid.uuid4(), code=code, name=name, is_enabled=True)
    db.add(row)
    await db.flush()
    return row


async def ensure_user(db: AsyncSession, username: str, display_name: str, role_name: str) -> User:
    existing = await get_one(db, User, username=username)
    if existing:
        return existing
    role = await get_one(db, Role, name=role_name)
    if role is None:
        raise RuntimeError(f"Missing role {role_name}; run backend/seed.py first.")
    user = User(
        id=uuid.uuid4(),
        username=username,
        password_hash=hash_password("demo123456"),
        display_name=display_name,
        role_id=role.id,
        is_enabled=True,
    )
    db.add(user)
    await db.flush()
    return user


async def ensure_period(db: AsyncSession, year: int, month: int, status: str) -> Period:
    period = await get_one(db, Period, year=year, month=month)
    if period is None:
        period = Period(id=uuid.uuid4(), year=year, month=month, status=status)
        db.add(period)
        await db.flush()
    else:
        period.status = status
    return period


async def load_accounts(db: AsyncSession) -> dict[str, Account]:
    required = [
        "1001", "100201", "1122", "1403", "1405", "1601", "1602",
        "2001", "2202", "2211", "222101", "4001", "4104",
        "6001", "6401", "6403", "6601", "6602", "6603",
    ]
    rows = (await db.execute(select(Account).where(Account.code.in_(required)))).scalars().all()
    accounts = {row.code: row for row in rows}
    missing = sorted(set(required) - set(accounts))
    if missing:
        raise RuntimeError(f"Missing accounts {missing}; run backend/seed.py first.")
    return accounts


async def ensure_balance(
    db: AsyncSession,
    period: Period,
    account: Account,
    opening_debit: Decimal = Decimal("0"),
    opening_credit: Decimal = Decimal("0"),
) -> AccountBalance:
    balance = await get_one(db, AccountBalance, period_id=period.id, account_id=account.id)
    if balance:
        return balance
    balance = AccountBalance(
        id=uuid.uuid4(),
        period_id=period.id,
        account_id=account.id,
        opening_debit=opening_debit,
        opening_credit=opening_credit,
        current_debit=Decimal("0"),
        current_credit=Decimal("0"),
        closing_debit=opening_debit,
        closing_credit=opening_credit,
    )
    db.add(balance)
    await db.flush()
    return balance


def recalc_closing(balance: AccountBalance, account: Account) -> None:
    if account.dc_type == "D":
        net = (
            balance.opening_debit
            - balance.opening_credit
            + balance.current_debit
            - balance.current_credit
        )
        balance.closing_debit = max(net, Decimal("0"))
        balance.closing_credit = max(-net, Decimal("0"))
    else:
        net = (
            balance.opening_credit
            - balance.opening_debit
            + balance.current_credit
            - balance.current_debit
        )
        balance.closing_credit = max(net, Decimal("0"))
        balance.closing_debit = max(-net, Decimal("0"))


async def apply_entry_to_balance(
    db: AsyncSession,
    period: Period,
    account: Account,
    debit: Decimal,
    credit: Decimal,
) -> None:
    balance = await ensure_balance(db, period, account)
    balance.current_debit += debit
    balance.current_credit += credit
    recalc_closing(balance, account)


async def carry_balances_forward(
    db: AsyncSession,
    previous: Period,
    current: Period,
    accounts: dict[str, Account],
) -> None:
    prev_rows = (
        await db.execute(select(AccountBalance).where(AccountBalance.period_id == previous.id))
    ).scalars().all()
    for prev in prev_rows:
        account = next((acct for acct in accounts.values() if acct.id == prev.account_id), None)
        if account is None:
            account = (await db.execute(select(Account).where(Account.id == prev.account_id))).scalar_one()
        await ensure_balance(
            db,
            current,
            account,
            opening_debit=prev.closing_debit,
            opening_credit=prev.closing_credit,
        )


async def add_auxiliary(
    db: AsyncSession,
    entry: VoucherEntry,
    archives: dict[str, dict[str, object]],
    aux_type: Literal["部门", "个人", "单位", "项目"],
    code: str,
) -> None:
    kwargs = {"id": uuid.uuid4(), "entry_id": entry.id, "aux_type": aux_type}
    if aux_type == "部门":
        kwargs["department_id"] = archives["departments"][code].id
    elif aux_type == "个人":
        kwargs["individual_id"] = archives["individuals"][code].id
    elif aux_type == "单位":
        kwargs["counterparty_id"] = archives["counterparties"][code].id
    elif aux_type == "项目":
        kwargs["project_id"] = archives["projects"][code].id
    db.add(EntryAuxiliary(**kwargs))


async def create_voucher(
    db: AsyncSession,
    *,
    period: Period,
    voucher_no: str,
    voucher_date: date,
    creator: User,
    auditor: User,
    entries: list[dict],
    accounts: dict[str, Account],
    archives: dict[str, dict[str, object]],
    attachments: int = 1,
) -> Voucher:
    total_debit = sum((item["debit"] for item in entries), Decimal("0"))
    total_credit = sum((item["credit"] for item in entries), Decimal("0"))
    if total_debit != total_credit:
        raise RuntimeError(f"Unbalanced voucher {voucher_no}: {total_debit} != {total_credit}")

    voucher = Voucher(
        id=uuid.uuid4(),
        voucher_no=voucher_no,
        date=voucher_date,
        period_id=period.id,
        attachments=attachments,
        status="posted",
        creator_id=creator.id,
        auditor_id=auditor.id,
        posted_at=datetime.now(timezone.utc),
        source=DEMO_SOURCE,
        ai_conversation={"demo": True, "scenario": "small_business_mvp"},
    )
    db.add(voucher)
    await db.flush()

    for row_number, item in enumerate(entries, start=1):
        account = accounts[item["account"]]
        entry = VoucherEntry(
            id=uuid.uuid4(),
            voucher_id=voucher.id,
            row_number=row_number,
            account_id=account.id,
            summary=item["summary"],
            debit_amount=item["debit"],
            credit_amount=item["credit"],
            quantity=item.get("quantity"),
            price=item.get("price"),
        )
        db.add(entry)
        await db.flush()
        for aux in item.get("auxiliaries", []):
            await add_auxiliary(db, entry, archives, aux[0], aux[1])
        await apply_entry_to_balance(db, period, account, item["debit"], item["credit"])

    return voucher


async def add_bank_or_cash_journal(
    db: AsyncSession,
    voucher: Voucher,
    period: Period,
    account: Account,
    summary: str,
    debit: Decimal,
    credit: Decimal,
    balance: Decimal,
    counterparty: str | None = None,
) -> None:
    row_cls = CashJournal if account.code == "1001" else BankJournal
    db.add(row_cls(
        id=uuid.uuid4(),
        date=voucher.date,
        period_id=period.id,
        voucher_id=voucher.id,
        account_id=account.id,
        summary=summary,
        debit=debit,
        credit=credit,
        balance=balance,
        serial_no=voucher.voucher_no,
        counterparty=counterparty,
    ))


def entry(account: str, summary: str, debit: Decimal = Decimal("0"), credit: Decimal = Decimal("0"), **extra) -> dict:
    return {"account": account, "summary": summary, "debit": debit, "credit": credit, **extra}


async def seed_demo() -> None:
    engine = create_async_engine(DATABASE_URL)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as db:
        existing = await db.execute(select(func.count(Voucher.id)).where(Voucher.source == DEMO_SOURCE))
        existing_count = existing.scalar_one()
        if existing_count:
            print(f"Demo data already exists: {existing_count} demo vouchers found. No changes made.")
            await engine.dispose()
            return

        accounts = await load_accounts(db)
        admin = await get_one(db, User, username="admin")
        if admin is None:
            raise RuntimeError("Missing admin user; run backend/seed.py first.")
        auditor = await ensure_user(db, "demo_auditor", "演示审核员", "finance_manager")

        archives = {
            "departments": {code: await ensure_archive(db, Department, code, name) for code, name in DEPARTMENTS},
            "individuals": {code: await ensure_archive(db, Individual, code, name) for code, name in EMPLOYEES},
            "counterparties": {code: await ensure_archive(db, Counterparty, code, name) for code, name in COUNTERPARTIES},
            "projects": {code: await ensure_archive(db, Project, code, name) for code, name in PROJECTS},
        }

        periods: dict[int, Period] = {}
        for plan in MONTHS:
            periods[plan.month] = await ensure_period(
                db, 2026, plan.month, "open" if plan.month == 6 else "closed"
            )

        # Opening balances at 2026-01-01. Balanced at RMB 25.85M.
        jan = periods[1]
        opening = {
            "1001": (d("50000"), Decimal("0")),
            "100201": (d("8000000"), Decimal("0")),
            "1122": (d("6000000"), Decimal("0")),
            "1405": (d("4000000"), Decimal("0")),
            "1601": (d("9000000"), Decimal("0")),
            "1602": (Decimal("0"), d("1200000")),
            "2202": (Decimal("0"), d("3000000")),
            "2001": (Decimal("0"), d("8000000")),
            "4001": (Decimal("0"), d("12000000")),
            "4104": (Decimal("0"), d("2850000")),
        }
        for code, (opening_debit, opening_credit) in opening.items():
            await ensure_balance(db, jan, accounts[code], opening_debit, opening_credit)

        bank_balance = opening["100201"][0]
        cash_balance = opening["1001"][0]

        total_vouchers = 0
        for plan in MONTHS:
            period = periods[plan.month]
            if plan.month > 1:
                await carry_balances_forward(db, periods[plan.month - 1], period, accounts)

            serial = 1

            async def add(entries: list[dict], day: int, attachments: int = 1) -> Voucher:
                nonlocal serial, total_vouchers
                voucher_day = min(day, monthrange(2026, plan.month)[1])
                voucher = await create_voucher(
                    db,
                    period=period,
                    voucher_no=f"DEMO-2026-{plan.month:02d}-{serial:03d}",
                    voucher_date=date(2026, plan.month, voucher_day),
                    creator=admin,
                    auditor=auditor,
                    entries=entries,
                    accounts=accounts,
                    archives=archives,
                    attachments=attachments,
                )
                serial += 1
                total_vouchers += 1
                return voucher

            vat_a = (plan.revenue_a * Decimal("0.13")).quantize(MONEY)
            vat_b = (plan.revenue_b * Decimal("0.13")).quantize(MONEY)
            gross_a = plan.revenue_a + vat_a
            gross_b = plan.revenue_b + vat_b

            await add([
                entry("1122", "确认华北企业数字化项目服务收入", gross_a, auxiliaries=[("单位", "C001"), ("项目", "P001")]),
                entry("6001", "确认主营业务收入", credit=plan.revenue_a, auxiliaries=[("项目", "P001")]),
                entry("222101", "计提销项税额", credit=vat_a),
            ], 3, 2)
            await add([
                entry("1122", "确认华东渠道交付项目服务收入", gross_b, auxiliaries=[("单位", "C002"), ("项目", "P002")]),
                entry("6001", "确认主营业务收入", credit=plan.revenue_b, auxiliaries=[("项目", "P002")]),
                entry("222101", "计提销项税额", credit=vat_b),
            ], 5, 2)

            receipt = plan.customer_receipt
            voucher = await add([
                entry("100201", "收到客户项目回款", receipt, auxiliaries=[("单位", "C001")]),
                entry("1122", "冲减应收账款", credit=receipt, auxiliaries=[("单位", "C001")]),
            ], 10, 1)
            bank_balance += receipt
            await add_bank_or_cash_journal(db, voucher, period, accounts["100201"], "收到客户项目回款", receipt, Decimal("0"), bank_balance, "北京星河智能科技有限公司")

            input_vat = (plan.purchase * Decimal("0.13")).quantize(MONEY)
            purchase_gross = plan.purchase + input_vat
            await add([
                entry("1405", "采购项目交付所需设备及材料", plan.purchase, quantity=Decimal("1000.0000"), price=(plan.purchase / Decimal("1000")).quantize(Decimal("0.0001")), auxiliaries=[("单位", "S001")]),
                entry("222101", "取得进项税额", input_vat),
                entry("2202", "确认供应商应付款", credit=purchase_gross, auxiliaries=[("单位", "S001")]),
            ], 11, 3)

            voucher = await add([
                entry("2202", "支付供应商货款", plan.supplier_payment, auxiliaries=[("单位", "S001")]),
                entry("100201", "银行支付供应商货款", credit=plan.supplier_payment),
            ], 13, 1)
            bank_balance -= plan.supplier_payment
            await add_bank_or_cash_journal(db, voucher, period, accounts["100201"], "支付供应商货款", Decimal("0"), plan.supplier_payment, bank_balance, "北京华采电子有限公司")

            await add([
                entry("6401", "结转本月主营业务成本", plan.cogs, auxiliaries=[("项目", "P001")]),
                entry("1405", "结转库存商品成本", credit=plan.cogs, quantity=Decimal("760.0000"), price=(plan.cogs / Decimal("760")).quantize(Decimal("0.0001"))),
            ], 18, 1)

            payroll_cogs = (plan.payroll * Decimal("0.28")).quantize(MONEY)
            payroll_sales = (plan.payroll * Decimal("0.27")).quantize(MONEY)
            payroll_admin = plan.payroll - payroll_cogs - payroll_sales
            await add([
                entry("6401", "计提交付人员薪酬", payroll_cogs, auxiliaries=[("部门", "D004")]),
                entry("6601", "计提销售人员薪酬", payroll_sales, auxiliaries=[("部门", "D003")]),
                entry("6602", "计提管理及后台人员薪酬", payroll_admin, auxiliaries=[("部门", "D002")]),
                entry("2211", "计提本月应付职工薪酬", credit=plan.payroll),
            ], 20, 1)

            salary_paid = (plan.payroll * Decimal("0.96")).quantize(MONEY)
            voucher = await add([
                entry("2211", "发放本月工资及社保公积金", salary_paid),
                entry("100201", "银行代发工资", credit=salary_paid),
            ], 22, 1)
            bank_balance -= salary_paid
            await add_bank_or_cash_journal(db, voucher, period, accounts["100201"], "银行代发工资", Decimal("0"), salary_paid, bank_balance, "员工薪酬")

            operating_expenses = [
                ("6601", "投放线上获客及展会推广费", plan.marketing, "S003", "D003", 23),
                ("6602", "支付办公室租金及物业费", plan.rent, "S005", "D005", 24),
                ("6602", "支付办公软件订阅及云服务费", plan.office, "S003", "D006", 25),
                ("6603", "支付贷款利息及银行手续费", plan.interest, "S006", "D002", 26),
            ]
            for acct, summary, amount, counterparty_code, dept_code, day in operating_expenses:
                voucher = await add([
                    entry(acct, summary, amount, auxiliaries=[("部门", dept_code), ("单位", counterparty_code)]),
                    entry("100201", summary, credit=amount),
                ], day, 1)
                bank_balance -= amount
                await add_bank_or_cash_journal(db, voucher, period, accounts["100201"], summary, Decimal("0"), amount, bank_balance, archives["counterparties"][counterparty_code].name)

            voucher = await add([
                entry("6601", "销售人员差旅报销", plan.travel, auxiliaries=[("个人", "E006"), ("部门", "D003")]),
                entry("1001", "现金支付差旅报销", credit=plan.travel),
            ], 27, 4)
            cash_balance -= plan.travel
            await add_bank_or_cash_journal(db, voucher, period, accounts["1001"], "现金支付差旅报销", Decimal("0"), plan.travel, cash_balance, "员工报销")

            await add([
                entry("6602", "计提本月固定资产折旧", plan.depreciation, auxiliaries=[("部门", "D005")]),
                entry("1602", "累计折旧", credit=plan.depreciation),
            ], 28, 1)

            await add([
                entry("6403", "计提城建税及教育费附加", plan.tax_surcharge),
                entry("222101", "计提附加税费", credit=plan.tax_surcharge),
            ], 29, 1)

            voucher = await add([
                entry("222101", "缴纳增值税及附加税费", plan.tax_payment),
                entry("100201", "银行缴纳税费", credit=plan.tax_payment),
            ], 30, 1)
            bank_balance -= plan.tax_payment
            await add_bank_or_cash_journal(db, voucher, period, accounts["100201"], "银行缴纳税费", Decimal("0"), plan.tax_payment, bank_balance, "国家税务总局")

            if plan.month == 1:
                voucher = await add([
                    entry("100201", "取得短期流动资金借款", d("2000000")),
                    entry("2001", "确认短期借款", credit=d("2000000")),
                ], 8, 1)
                bank_balance += d("2000000")
                await add_bank_or_cash_journal(db, voucher, period, accounts["100201"], "取得短期流动资金借款", d("2000000"), Decimal("0"), bank_balance, "招商银行北京分行")

            if plan.month == 3:
                voucher = await add([
                    entry("1601", "购置交付测试设备", d("420000"), auxiliaries=[("部门", "D004")]),
                    entry("100201", "银行支付设备采购款", credit=d("420000")),
                ], 16, 2)
                bank_balance -= d("420000")
                await add_bank_or_cash_journal(db, voucher, period, accounts["100201"], "银行支付设备采购款", Decimal("0"), d("420000"), bank_balance, "苏州启明设备有限公司")

        await seed_fixed_assets(db, archives)
        await db.commit()
        print(
            "Demo import done: "
            f"{total_vouchers} posted vouchers, {len(DEPARTMENTS)} departments, "
            f"{len(EMPLOYEES)} employees, {len(COUNTERPARTIES)} counterparties, "
            f"{len(PROJECTS)} projects, and demo fixed assets."
        )
        print("Demo period: 2026-06 is open; 2026-01..2026-05 are closed.")
        print("Demo auditor login: demo_auditor / demo123456")

    await engine.dispose()


async def seed_fixed_assets(db: AsyncSession, archives: dict[str, dict[str, object]]) -> None:
    assets = [
        ("FA-2024-001", "办公区服务器集群", "电子设备", date(2024, 5, 20), d("1280000"), d("64000"), 60, d("405333.36"), "D006"),
        ("FA-2024-002", "员工笔记本电脑批次A", "办公设备", date(2024, 8, 12), d("760000"), d("38000"), 36, d("321000.00"), "D005"),
        ("FA-2025-001", "客户演示大屏及会议系统", "办公设备", date(2025, 3, 8), d("320000"), d("16000"), 60, d("66000.00"), "D003"),
        ("FA-2025-002", "交付测试设备", "专用设备", date(2025, 11, 18), d("920000"), d("46000"), 72, d("85000.00"), "D004"),
        ("FA-2026-001", "项目测试一体机", "专用设备", date(2026, 3, 16), d("420000"), d("21000"), 60, d("21000.00"), "D004"),
    ]
    for code, name, category, purchase_date, amount, salvage, life, accumulated, dept_code in assets:
        existing = await get_one(db, FixedAsset, code=code)
        monthly = ((amount - salvage) / Decimal(life)).quantize(MONEY)
        net_value = amount - accumulated
        if existing:
            continue
        db.add(FixedAsset(
            id=uuid.uuid4(),
            code=code,
            name=name,
            category=category,
            purchase_date=purchase_date,
            purchase_amount=amount,
            salvage_value=salvage,
            useful_life_months=life,
            depreciation_method="straight",
            monthly_depreciation=monthly,
            accumulated_depreciation=accumulated,
            net_value=net_value,
            status="in_use",
            dept_id=archives["departments"][dept_code].id,
        ))


if __name__ == "__main__":
    asyncio.run(seed_demo())
