"""factory_boy fixtures for test data generation.

All factories produce dicts that are used to construct ORM model instances.
Uses factory_boy with SQLAlchemy async support.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import factory


class RoleDictFactory(factory.Factory):
    """Role dict factory."""

    class Meta:
        model = dict

    id = factory.LazyFunction(uuid.uuid4)
    name = "finance_manager"
    permissions = factory.LazyFunction(lambda: {
        "voucher:create": True,
        "voucher:edit:own": True,
        "voucher:audit": True,
        "voucher:post": True,
        "voucher:reverse": True,
        "voucher:delete:draft": True,
        "voucher:edit:any": True,
        "voucher:unaudit": True,
        "account:read": True,
        "account:manage": True,
        "ledger:read": True,
        "report:read": True,
        "report:export": True,
        "period:close": True,
        "period:reopen": True,
        "aux:manage": True,
        "cashier:use": True,
        "assets:manage": True,
        "ai:use": True,
        "admin:users": True,
        "admin:roles": True,
        "admin:backup": True,
        "admin:audit-log": True,
    })


class UserDictFactory(factory.Factory):
    """User dict factory."""

    class Meta:
        model = dict

    id = factory.LazyFunction(uuid.uuid4)
    username = factory.Sequence(lambda n: f"testuser{n}")
    password_hash = "$2b$12$testhashplaceholder"
    display_name = factory.Sequence(lambda n: f"Test User {n}")
    role_id = factory.LazyFunction(uuid.uuid4)
    is_enabled = True
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class AccountDictFactory(factory.Factory):
    """Account dict factory."""

    class Meta:
        model = dict

    id = factory.LazyFunction(uuid.uuid4)
    code = factory.Sequence(lambda n: f"{1000 + n}")
    name = factory.Sequence(lambda n: f"Test Account {n}")
    parent_id = None
    level = 1
    type = "asset"
    dc_type = "D"
    is_cash = False
    is_enabled = True
    aux_types = factory.LazyFunction(list)


class PeriodDictFactory(factory.Factory):
    """Period dict factory."""

    class Meta:
        model = dict

    id = factory.LazyFunction(uuid.uuid4)
    year = 2026
    month = 6
    status = "open"


class VoucherDictFactory(factory.Factory):
    """Voucher dict factory."""

    class Meta:
        model = dict

    id = factory.LazyFunction(uuid.uuid4)
    voucher_no = factory.Sequence(lambda n: f"JZ-2026-06-{n + 1:03d}")
    date = date(2026, 6, 15)
    period_id = factory.LazyFunction(uuid.uuid4)
    attachments = 0
    status = "draft"
    creator_id = factory.LazyFunction(uuid.uuid4)
    source = "manual"


class EntryDictFactory(factory.Factory):
    """VoucherEntry dict factory."""

    class Meta:
        model = dict

    id = factory.LazyFunction(uuid.uuid4)
    voucher_id = factory.LazyFunction(uuid.uuid4)
    row_number = 1
    account_id = factory.LazyFunction(uuid.uuid4)
    summary = "Test entry"
    debit_amount = Decimal("5000.00")
    credit_amount = Decimal("0")
    quantity = None
    price = None


class AccountBalanceDictFactory(factory.Factory):
    """AccountBalance dict factory."""

    class Meta:
        model = dict

    id = factory.LazyFunction(uuid.uuid4)
    period_id = factory.LazyFunction(uuid.uuid4)
    account_id = factory.LazyFunction(uuid.uuid4)
    opening_debit = Decimal("0")
    opening_credit = Decimal("0")
    current_debit = Decimal("0")
    current_credit = Decimal("0")
    closing_debit = Decimal("0")
    closing_credit = Decimal("0")


class CarryTemplateDictFactory(factory.Factory):
    """CarryTemplate dict factory."""

    class Meta:
        model = dict

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"结转模板{n}")
    description = "Test carry template"
    rules = factory.LazyFunction(lambda: {
        "from_accounts": [],
        "to_account": "",
        "formula": "closing_balance",
    })
    sort_order = 0
    is_enabled = True


class VoucherTemplateDictFactory(factory.Factory):
    """VoucherTemplate dict factory."""

    class Meta:
        model = dict

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"凭证模板{n}")
    description = "Test voucher template"
    category = "payment"
    entries = factory.LazyFunction(list)
    is_enabled = True
