"""API v1 — main router aggregating all sub-routers.

Router map:
- /auth         → auth routes (§3.2)
- /vouchers     → voucher CRUD + workflow (§3.3)
- /voucher-templates → template CRUD (§3.4)
- /accounts     → chart of accounts (§3.5)
- /reports      → ledger reports (§3.6)
- /statements   → financial statements (§3.7)
- /periods      → accounting periods (§3.8)
- /carry-forward → carry-forward (§3.8)
- /auxiliaries  → auxiliary核算 (§3.9)
- /cash-journals / /bank-journals / /bank-reconcile → cashier (§3.10)
- /fixed-assets → fixed assets (§3.11)
- /ai           → AI features (§3.12)
- /admin        → system administration (§3.13)
- /dashboard    → dashboard summary (§3.14)
- /health       → health check (§3.14)
"""

from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    admin,
    ai,
    auth,
    auxiliaries,
    bank_journals,
    bank_reconcile,
    cash_journals,
    dashboard,
    fixed_assets,
    health,
    original_documents,
    periods,
    reports,
    voucher_templates,
    vouchers,
)

api_router = APIRouter()

# §3.2 — Authentication
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# §3.3 — Vouchers
api_router.include_router(vouchers.router, prefix="/vouchers", tags=["vouchers"])

# §3.4 — Voucher Templates
api_router.include_router(
    voucher_templates.router, prefix="/voucher-templates", tags=["voucher-templates"]
)

# §3.5 — Accounts
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])

# §3.6 — Reports (ledgers)
api_router.include_router(reports.report_router, prefix="/reports", tags=["reports"])

# §3.7 — Financial Statements
api_router.include_router(reports.statement_router, prefix="/statements", tags=["statements"])

# §3.8 — Periods
api_router.include_router(periods.router, prefix="/periods", tags=["periods"])
api_router.include_router(periods.carry_forward_router, prefix="/carry-forward", tags=["carry-forward"])

# §3.9 — Auxiliary核算
api_router.include_router(auxiliaries.router, prefix="/auxiliaries", tags=["auxiliaries"])

# §3.10 — Cashier
api_router.include_router(cash_journals.router, prefix="/cash-journals", tags=["cashier"])
api_router.include_router(bank_journals.router, prefix="/bank-journals", tags=["cashier"])
api_router.include_router(bank_reconcile.router, prefix="/bank-reconcile", tags=["cashier"])

# §3.11 — Fixed Assets
api_router.include_router(fixed_assets.router, prefix="/fixed-assets", tags=["assets"])

# §3.12 — AI
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])

# Original documents (原始凭证/票据附件)
api_router.include_router(
    original_documents.router,
    prefix="/original-documents",
    tags=["original-documents"],
)

# §3.13 — Admin
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

# §3.14 — Dashboard
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

# §3.14 — Health
api_router.include_router(health.router, prefix="/health", tags=["health"])
