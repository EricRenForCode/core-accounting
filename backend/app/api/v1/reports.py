"""Reports and financial statements routes (§3.6, §3.7).

Reports (§3.6):
  GET /reports/trial-balance              — 科目余额表
  GET /reports/general-ledger             — 总账
  GET /reports/detail-ledger/{account_id} — 三栏明细账
  GET /reports/multi-column-ledger/{account_id} — 多栏明细账
  GET /reports/journal                    — 序时账
  GET /reports/quantity-ledger/{account_id}   — 数量金额账

Statements (§3.7):
  GET  /statements/balance-sheet — 资产负债表
  GET  /statements/income        — 利润表
  GET  /statements/cash-flow     — 现金流量表
  GET  /statements/templates     — 报表模板列表
  POST /statements/export        — 导出报表
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.schemas.report import (
    BalanceSheetResponse,
    CashFlowStatementResponse,
    DetailLedgerResponse,
    GeneralLedgerResponse,
    IncomeStatementResponse,
    JournalResponse,
    QuantityLedgerResponse,
    StatementExportRequest,
    TrialBalanceResponse,
)

report_router = APIRouter()
statement_router = APIRouter()


# ── Reports (§3.6) ────────────────────────────────────────────


@report_router.get("/trial-balance", response_model=TrialBalanceResponse)
async def trial_balance(
    period_id: UUID = Query(...),
    level: int = Query(None, ge=1, le=4),
    include_zero: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:read")),
) -> TrialBalanceResponse:
    """科目余额表 — trial balance with tree structure.

    Logic (§7.2):
    1. Check Redis cache: key=f"trial-balance:{period_id}:{level}"
    2. If cached, return cached result
    3. Query AccountBalance WHERE period_id=...
    4. Query all enabled accounts
    5. Build tree structure with opening/closing balances
    6. Calculate direction-aware closing: D-type or C-type
    7. Compute summary row (totals)
    8. Cache result in Redis (TTL=300s)
    """
    raise NotImplementedError(
        "trial_balance — §7.2:\n"
        "1. cache_key = f'trial-balance:{period_id}:{level}'\n"
        "2. Check redis.get(cache_key) → return if hit\n"
        "3. balances = SELECT * FROM account_balances WHERE period_id=...\n"
        "4. accounts = SELECT * FROM accounts WHERE is_enabled=TRUE\n"
        "5. Build map: account_id → AccountBalance\n"
        "6. Build tree: root accounts (parent_id=NULL), recursively attach children\n"
        "7. For each node: set opening/closing based on dc_type\n"
        "   - D-type: opening_balance = opening_debit - opening_credit (display as debit)\n"
        "   - C-type: opening_balance = opening_credit - opening_debit (display as credit)\n"
        "8. Filter by level if specified (prune tree)\n"
        "9. If not include_zero: filter out rows with all-zero balances\n"
        "10. Compute summary totals\n"
        "11. Cache result, TTL=300\n"
        "12. Return TrialBalanceResponse"
    )


@report_router.get("/general-ledger", response_model=GeneralLedgerResponse)
async def general_ledger(
    period_id: UUID = Query(...),
    account_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ledger:read")),
) -> GeneralLedgerResponse:
    """总账 — general ledger for a single account in a period.

    Shows opening balance, each transaction, and closing balance.
    """
    raise NotImplementedError(
        "general_ledger:\n"
        "1. Get account by ID (404 if missing)\n"
        "2. Get AccountBalance for period: opening\n"
        "3. Query voucher_entries for this account within period\n"
        "   - JOIN vouchers WHERE vouchers.period_id=... AND status='posted'\n"
        "   - ORDER BY vouchers.date, vouchers.voucher_no\n"
        "4. Calculate running balance based on account.dc_type\n"
        "5. Return GeneralLedgerResponse"
    )


@report_router.get("/detail-ledger/{account_id}", response_model=DetailLedgerResponse)
async def detail_ledger(
    account_id: UUID,
    period_id: UUID = Query(...),
    date_from: str = Query(None),
    date_to: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ledger:read")),
) -> DetailLedgerResponse:
    """三栏明细账 — three-column detail ledger.

    Columns: date, voucher_no, summary, debit, credit, balance_direction, balance.
    """
    raise NotImplementedError(
        "detail_ledger:\n"
        "1. Get account by ID\n"
        "2. Get opening balance from AccountBalance\n"
        "3. Query posted voucher_entries for this account within period + date range\n"
        "4. Calculate running balance row by row\n"
        "5. Return DetailLedgerResponse with opening, rows, closing"
    )


@report_router.get("/multi-column-ledger/{account_id}")
async def multi_column_ledger(
    account_id: UUID,
    period_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ledger:read")),
) -> dict:
    """多栏明细账 — multi-column detail ledger with auxiliary核算 breakdown.

    Columns are dynamically generated based on the account's aux_types.
    For example, if aux_types=["部门"], columns are department names.
    """
    raise NotImplementedError(
        "multi_column_ledger:\n"
        "1. Get account, read aux_types\n"
        "2. For each aux_type, query all distinct aux entity values\n"
        "3. Query vouchers with entries for this account, joined with entry_auxiliaries\n"
        "4. Pivot: each row is one voucher, columns = aux entities, values = debit/credit\n"
        "5. Return dynamic-column response"
    )


@report_router.get("/journal", response_model=JournalResponse)
async def journal(
    period_id: UUID = Query(...),
    date_from: str = Query(None),
    date_to: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ledger:read")),
) -> JournalResponse:
    """序时账 — chronological journal listing all posted entries.

    All entries for the period in date+voucher_no order.
    """
    raise NotImplementedError(
        "journal:\n"
        "1. Query posted voucher_entries joined with vouchers\n"
        "   WHERE vouchers.period_id=... AND status='posted' AND deleted_at IS NULL\n"
        "   Optional date_from/date_to range filter\n"
        "   JOIN accounts ON voucher_entries.account_id=accounts.id\n"
        "2. ORDER BY vouchers.date, vouchers.voucher_no, voucher_entries.row_number\n"
        "3. Calculate total_debit and total_credit\n"
        "4. Return JournalResponse"
    )


@report_router.get("/quantity-ledger/{account_id}", response_model=QuantityLedgerResponse)
async def quantity_ledger(
    account_id: UUID,
    period_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("ledger:read")),
) -> QuantityLedgerResponse:
    """数量金额账 — quantity and amount ledger for inventory-type accounts.

    Only applicable for accounts with is_quantity=True.
    Shows quantity_in, quantity_out, quantity_balance alongside amounts.
    """
    raise NotImplementedError(
        "quantity_ledger:\n"
        "1. Get account, verify is_quantity=TRUE → 400 if not\n"
        "2. Query posted entries with quantity/price data\n"
        "3. Calculate running quantity and amount balances\n"
        "4. Return QuantityLedgerResponse"
    )


# ── Financial Statements (§3.7) ───────────────────────────────


@statement_router.get("/balance-sheet", response_model=BalanceSheetResponse)
async def balance_sheet(
    period_id: UUID = Query(...),
    template_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:read")),
) -> BalanceSheetResponse:
    """资产负债表 — balance sheet.

    Structure: assets (current/non-current), liabilities (current/non-current), equity.
    """
    raise NotImplementedError(
        "balance_sheet:\n"
        "1. Load statement template (or use default)\n"
        "2. Get period balances for all accounts\n"
        "3. Map accounts to template sections via account type\n"
        "4. Compute subtotals and totals\n"
        "5. Verify assets == liabilities + equity\n"
        "6. Return BalanceSheetResponse"
    )


@statement_router.get("/income", response_model=IncomeStatementResponse)
async def income_statement(
    period_id: UUID = Query(...),
    template_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:read")),
) -> IncomeStatementResponse:
    """利润表 — income / profit & loss statement."""
    raise NotImplementedError(
        "income_statement:\n"
        "1. Load template\n"
        "2. Get period balances for revenue/expense accounts\n"
        "3. Map to template sections (revenue → cost → gross profit → expenses → net profit)\n"
        "4. Return IncomeStatementResponse"
    )


@statement_router.get("/cash-flow", response_model=CashFlowStatementResponse)
async def cash_flow(
    period_id: UUID = Query(...),
    template_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:read")),
) -> CashFlowStatementResponse:
    """现金流量表 — cash flow statement.

    Sections: operating, investing, financing activities.
    """
    raise NotImplementedError(
        "cash_flow:\n"
        "1. Load template\n"
        "2. Query cash account movements for the period\n"
        "3. Categorize by activity type (operating/investing/financing)\n"
        "4. Return CashFlowStatementResponse"
    )


@statement_router.get("/templates")
async def statement_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:read")),
) -> list[dict]:
    """List available financial statement templates."""
    raise NotImplementedError(
        "statement_templates:\n"
        "1. Return list of built-in templates: 一般企业, 小企业, etc.\n"
        "2. Each template has {id, name, type, sections}"
    )


@statement_router.post("/export")
async def export_statement(
    body: StatementExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("report:export")),
) -> dict:
    """Export a financial statement as Excel or PDF.

    Body: {type: 'balance_sheet'|'income'|'cash_flow', period_id, format: 'excel'|'pdf'}
    """
    raise NotImplementedError(
        "export_statement:\n"
        "1. Generate the statement data (balance_sheet/income/cash_flow)\n"
        "2. If format=excel: build with openpyxl (formatted cells, headers, subtotals)\n"
        "3. If format=pdf: render HTML template → PDF with weasyprint\n"
        "4. Return StreamingResponse with appropriate Content-Type"
    )
