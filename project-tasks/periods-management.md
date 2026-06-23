# P2.3 会计期间管理 — Task List

> Generated: 2026-06-18 | Project: core-accounting
> Phase: P2.3 会计期间管理
> Reference: engineering-spec.md §2.6, §3.8, §7.4

---

## Task 1: Backend API — Period CRUD Endpoints

**File**: `backend/app/api/v1/periods.py`, `backend/app/schemas/period.py`
**Status**: [x]

### 1.1 GET /periods — List periods ✅
- Query with optional year and status filters
- Order by year DESC, month DESC
- Return PeriodListResponse

### 1.2 GET /periods/current — Current open period ✅
- SELECT open period ORDER BY year ASC, month ASC
- Fallback to latest period if none open
- 404 if no periods exist

### 1.3 POST /periods — Create period ✅
- New PeriodCreate schema added (year, month)
- Duplicate check (409)
- Auto carry-forward opening balances from previous month

### 1.4 POST /periods/{id}/close — Close period (§7.4) ✅
- Row lock with `with_for_update()`
- Verify status == 'open' (409 if already closed)
- Check for audited-but-unposted vouchers (409)
- Carry forward closing → next period opening balances
- Set closed_at, closed_by

### 1.5 POST /periods/{id}/reopen — Reopen period ✅
- Row lock with `with_for_update()`
- Verify status == 'closed' (409)
- Delete next period's carried-forward balances
- Clear closed_at, closed_by

### 1.6 GET /periods/{id}/trial-balance — Trial balance check ✅
- Sum current_debit and current_credit across all AccountBalances
- Return {is_balanced, total_debit, total_credit, difference}

---

## Task 2: Frontend — Period Management Page

**File**: `frontend/src/features/admin/PeriodManage.tsx`, `frontend/src/routeTree.tsx`
**Status**: [x]

### 2.1 PeriodManage Component ✅
- Page title "会计期间管理" with subtitle
- "创建期间" button (period:close permission gated)
- Year-grouped collapsible sections
- Period cards: year-month, status badge (开放/已结账), action buttons
- Current period highlighted with accent border + "当前期间" label

### 2.2 Create Period Dialog ✅
- Year (2000-2100) + month select
- Duplicate validation
- POST /periods

### 2.3 Close Period Dialog ✅
- Live trial balance fetch from GET /periods/{id}/trial-balance
- Shows debit/credit/difference/balance status
- Warning when unbalanced
- Confirmation with descriptive text

### 2.4 Reopen Period Dialog ✅
- Admin only (period:reopen permission)
- ConfirmDialog with danger variant
- Warning about deleting carry-forward balances

### 2.5 Trial Balance Quick View ✅
- Expandable per-card panel
- Shows 借方合计/贷方合计/差额/状态

### 2.6 Route Wiring ✅
- PeriodManage imported and wired to /admin/periods

---

## Verification

| Check | Result |
|---|---|
| Backend Python syntax | ✅ No errors |
| Frontend TypeScript | ✅ No errors (tsc --noEmit) |
| Route wiring | ✅ PeriodManage at /admin/periods |
| close_period uses with_for_update() | ✅ |
| close_period checks unposted vouchers | ✅ |
| close_period carries forward balances | ✅ |
| reopen_period cleans up carry-forward | ✅ |
| trial-balance sums AccountBalance | ✅ |
