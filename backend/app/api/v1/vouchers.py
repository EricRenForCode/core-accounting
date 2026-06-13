"""Voucher routes (§3.3) — 12 endpoints for full voucher lifecycle.

GET    /vouchers          — list with filtering
POST   /vouchers          — create voucher
GET    /vouchers/{id}     — detail with entries + auxiliaries
PUT    /vouchers/{id}     — update (draft only)
DELETE /vouchers/{id}     — soft delete (draft only)
POST   /vouchers/{id}/audit   — audit
POST   /vouchers/{id}/unaudit — unaudit
POST   /vouchers/{id}/post    — post to ledger
POST   /vouchers/{id}/reverse — reverse voucher
GET    /vouchers/{id}/print   — print data
POST   /vouchers/import       — batch import (Excel)
GET    /vouchers/export       — batch export (Excel)
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.voucher import (
    CreateVoucherRequest,
    ExportVoucherRequest,
    ImportVoucherRequest,
    UpdateVoucherRequest,
    VoucherListParams,
    VoucherResponse,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[VoucherResponse])
async def list_vouchers(
    params: VoucherListParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[VoucherResponse]:
    """List vouchers with filtering, sorting, and pagination.

    Filters: date_from, date_to, status, keyword (searches voucher_no + entries.summary),
             period_id
    """
    raise NotImplementedError(
        "list_vouchers — §7 Business Logic:\n"
        "1. Build SQLAlchemy query with dynamic filters (date_from/to, status, keyword ILIKE, period_id)\n"
        "2. keyword searches voucher_no, entries.summary via subquery\n"
        "3. Apply sort (date/created_at/voucher_no) and order (asc/desc)\n"
        "4. Paginate with page/page_size\n"
        "5. Return PaginatedResponse with VoucherResponse items\n"
        "6. Exclude soft-deleted vouchers (deleted_at IS NULL)"
    )


@router.post("", response_model=VoucherResponse, status_code=201)
async def create_voucher(
    body: CreateVoucherRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:create")),
) -> VoucherResponse:
    """Create a new voucher (draft status).

    Logic (§7.1 — voucher creation):
    1. Validate period is open
    2. Generate voucher_no: JZ-{year}-{month}-{serial} (use DB sequence or row lock)
    3. Create Voucher with status="draft", creator_id=current_user.id
    4. Create VoucherEntry rows from body.entries
    5. XOR check: each entry has exactly one of debit/credit > 0
    6. Total debit must equal total credit (enforced by CreateVoucherRequest validator)
    7. Create EntryAuxiliary rows if entries have auxiliaries
    8. Commit and return created voucher with entries
    """
    raise NotImplementedError(
        "create_voucher — §7.1:\n"
        "1. validate_period_open(period_id) — SELECT period WHERE id=... AND status='open'\n"
        "2. generate_voucher_no(period.year, period.month) — lock+increment serial\n"
        "3. voucher = Voucher(date=..., period_id=..., creator_id=..., status='draft', source='manual')\n"
        "4. for entry in entries: VoucherEntry(voucher_id=..., row_number=..., account_id=..., summary=..., debit/credit=..., quantity/price)\n"
        "5. for aux in entry.auxiliaries: EntryAuxiliary(entry_id=..., aux_type=..., department_id/individual_id/...)\n"
        "6. db.add_all([voucher, entries, auxiliaries])\n"
        "7. Return VoucherResponse with nested entries"
    )


@router.get("/{voucher_id}", response_model=VoucherResponse)
async def get_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoucherResponse:
    """Get voucher detail with entries and auxiliary核算 references.

    Returns 404 if voucher not found or soft-deleted.
    """
    raise NotImplementedError(
        "get_voucher:\n"
        "1. SELECT voucher + joined entries + entry_auxiliaries WHERE id=voucher_id AND deleted_at IS NULL\n"
        "2. Return VoucherResponse with nested VoucherEntryResponse + auxiliaries\n"
        "3. 404 if not found"
    )


@router.put("/{voucher_id}", response_model=VoucherResponse)
async def update_voucher(
    voucher_id: UUID,
    body: UpdateVoucherRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoucherResponse:
    """Update voucher (only if status=draft).

    Permission: voucher:edit:own (own vouchers) or voucher:edit:any (all).
    """
    raise NotImplementedError(
        "update_voucher:\n"
        "1. SELECT voucher WHERE id=... AND deleted_at IS NULL\n"
        "2. Assert voucher.status == 'draft' → else 409 VOUCHER_NOT_DRAFT\n"
        "3. Permission check: if not has 'voucher:edit:any' and voucher.creator_id != current_user.id → 403\n"
        "4. If body.entries provided: delete old entries, recreate from body\n"
        "5. Update date, attachments fields\n"
        "6. Return updated voucher"
    )


@router.delete("/{voucher_id}")
async def delete_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Soft-delete a draft voucher (sets deleted_at).

    Permission: voucher:delete:draft
    """
    raise NotImplementedError(
        "delete_voucher:\n"
        "1. SELECT voucher WHERE id=... AND deleted_at IS NULL\n"
        "2. Assert voucher.status == 'draft' → else 409\n"
        "3. Set voucher.deleted_at = utcnow()\n"
        "4. Return {message: 'Voucher deleted'}"
    )


@router.post("/{voucher_id}/audit", response_model=VoucherResponse)
async def audit_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:audit")),
) -> VoucherResponse:
    """Audit a draft voucher (status: draft → audited).

    Logic (§7.1 pre-condition):
    1. Verify voucher exists and status=draft
    2. Verify voucher is balanced (total debit == total credit)
    3. Verify period is open
    4. Set status='audited', auditor_id=current_user.id
    5. Return voucher
    """
    raise NotImplementedError(
        "audit_voucher:\n"
        "1. voucher = SELECT WHERE id=... AND deleted_at IS NULL\n"
        "2. assert voucher.status == 'draft' → 409\n"
        "3. Verify balance: sum(entries.debit) == sum(entries.credit) → else 409 UNBALANCED_VOUCHER\n"
        "4. Assert period.status == 'open'\n"
        "5. voucher.status = 'audited'; voucher.auditor_id = current_user.id\n"
        "6. Commit, return voucher"
    )


@router.post("/{voucher_id}/unaudit", response_model=VoucherResponse)
async def unaudit_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:unaudit")),
) -> VoucherResponse:
    """Reverse audit: audited → draft.

    Only allowed if voucher has not been posted.
    """
    raise NotImplementedError(
        "unaudit_voucher:\n"
        "1. voucher = SELECT WHERE id=... AND deleted_at IS NULL\n"
        "2. assert voucher.status == 'audited' → 409\n"
        "3. assert voucher.posted_at IS NULL → 409\n"
        "4. voucher.status = 'draft'; voucher.auditor_id = None\n"
        "5. Return voucher"
    )


@router.post("/{voucher_id}/post", response_model=VoucherResponse)
async def post_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:post")),
) -> VoucherResponse:
    """Post a voucher to the ledger (status: audited → posted).

    Full logic in §7.1 — this is the core accounting operation:
    1. Verify voucher.status == 'audited'
    2. Lock period row (SELECT FOR UPDATE) to prevent concurrent close
    3. Verify period is open
    4. Set voucher.status = 'posted', posted_at = NOW()
    5. Aggregate entries by account_id
    6. For each account: upsert AccountBalance with row-level lock
       - Increment current_debit/current_credit
       - Recalculate closing_debit/closing_credit based on account.dc_type
    7. Write audit log entry
    8. Invalidate trial-balance cache for this period
    """
    raise NotImplementedError(
        "post_voucher — §7.1 full pseudocode:\n"
        "async with db.transaction():\n"
        "  period = SELECT ... FOR UPDATE → assert open\n"
        "  voucher.status = 'posted'; voucher.posted_at = utcnow()\n"
        "  account_totals = aggregate entries by account_id\n"
        "  for each account: upsert AccountBalance (SELECT FOR UPDATE)\n"
        "    - increment current_debit/current_credit\n"
        "    - recalculate closing based on dc_type\n"
        "    - D-type: closing_debit = opening_debit + current_debit - current_credit\n"
        "    - C-type: closing_credit = opening_credit + current_credit - current_debit\n"
        "  audit('voucher:post', voucher_id)\n"
        "  cache.delete_pattern(f'trial-balance:{period.id}*')"
    )


@router.post("/{voucher_id}/reverse", response_model=VoucherResponse)
async def reverse_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("voucher:reverse")),
) -> VoucherResponse:
    """Reverse a posted voucher — creates a new voucher with negated entries.

    Logic:
    1. Verify original voucher.status == 'posted'
    2. Create new voucher with same entries but debit↔credit swapped
    3. Set source='reversal', reversed_voucher_id=original.id
    4. Set reversal_type='full' (or 'partial' if supported)
    5. Original voucher.status = 'reversed'
    6. Auto-post the reversal voucher
    7. Return the new voucher
    """
    raise NotImplementedError(
        "reverse_voucher:\n"
        "1. original = SELECT WHERE id=... AND deleted_at IS NULL\n"
        "2. assert original.status == 'posted'\n"
        "3. reversal = Voucher(date=today, period=original.period, status='draft', source='reversal', reversed_voucher_id=original.id, reversal_type='full')\n"
        "4. For each entry: copy with debit↔credit swapped; summary = '[冲销] ' + original.summary\n"
        "5. Auto-audit and auto-post the reversal (or return as draft — config-dependent)\n"
        "6. original.status = 'reversed'\n"
        "7. Return reversal voucher"
    )


@router.get("/{voucher_id}/print")
async def print_voucher(
    voucher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get print-formatted voucher data (for PDF/print rendering)."""
    raise NotImplementedError(
        "print_voucher:\n"
        "1. Get voucher with entries, accounts, auxiliaries\n"
        "2. Format for print: company header, voucher no, date, entries table, signatures\n"
        "3. Return print-ready data structure"
    )


@router.post("/import")
async def import_vouchers(
    file: UploadFile,
    period_id: UUID = Query(...),
    override_existing: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Import vouchers from Excel file.

    Excel format: rows with voucher_no, date, account_codes, summaries, debit/credit amounts.
    """
    raise NotImplementedError(
        "import_vouchers:\n"
        "1. Parse Excel file (openpyxl)\n"
        "2. Validate header row matches expected columns\n"
        "3. For each row: look up account by code, validate amount format\n"
        "4. Group rows by voucher_no → create voucher + entries\n"
        "5. Validate balance for each voucher\n"
        "6. If override_existing: replace existing draft vouchers with same voucher_no\n"
        "7. Return {imported: N, skipped: M, errors: [...]}"
    )


@router.get("/export")
async def export_vouchers(
    params: ExportVoucherRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Export vouchers to Excel (same filter params as list).

    Returns a downloadable Excel file.
    """
    raise NotImplementedError(
        "export_vouchers:\n"
        "1. Run same query as list_vouchers (no pagination)\n"
        "2. Build Excel workbook (openpyxl)\n"
        "3. Header row: voucher_no, date, account_code, account_name, summary, debit, credit\n"
        "4. Return StreamingResponse with Content-Disposition"
    )
