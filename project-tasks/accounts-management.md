# 科目管理 (Account Management) — Task List

> Generated: 2026-06-18 | Project: core-accounting
> Focus: 会计系统基础数据 — Chart of Accounts CRUD

---

## Task 1: Backend API — List & Tree Endpoints

**File**: `backend/app/api/v1/accounts.py`
**Status**: [x]

### 1.1 GET /accounts — Flat list with filters & pagination ✅
- SQLAlchemy query with optional filters: `parent_id`, `type`, `is_enabled`
- Order by `code` ASC, paginate (page, page_size), count total
- Returns `AccountListResponse`

### 1.2 GET /accounts/tree — Nested tree structure ✅
- Fetch all accounts, build tree: roots have `parent_id=NULL`
- Recursively attach children via id→node map
- Returns `AccountTreeResponse` with all fields populated
- **QA fix**: Added `parent_id`, `is_cash`, `aux_types`, `is_quantity`, `quantity_unit` to tree nodes

---

## Task 2: Backend API — Create Endpoint

**File**: `backend/app/api/v1/accounts.py`
**Status**: [x]

### 2.1 POST /accounts — Create new account ✅
- Validate `code` uniqueness → 409 if conflict
- If `parent_id` provided: verify parent exists and `parent.level + 1 == body.level`
- If no parent and level==1: `parent_id=NULL`
- Create `Account(...)` and return `AccountSchema` (201)

---

## Task 3: Backend API — Update & Delete Endpoints

**File**: `backend/app/api/v1/accounts.py`
**Status**: [x]

### 3.1 PUT /accounts/{id} — Update account metadata ✅
- Get account by ID (404 if missing)
- Patch allowed fields only (not code/level/type/dc_type/parent_id)
- Returns updated `AccountSchema`

### 3.2 DELETE /accounts/{id} — Delete with safety checks ✅
- Check for child accounts → 409
- Check for voucher_entries referencing → 409 `ACCOUNT_HAS_VOUCHERS`
- Delete and return `{message: 'Account deleted'}`

---

## Task 4: Frontend — Account Management Page

**Files**: `frontend/src/features/admin/AccountsPage.tsx`, `frontend/src/routeTree.tsx`, `frontend/src/types/account.ts`
**Status**: [x]

### 4.1 AccountsPage Component ✅
- Tree table with expand/collapse, type filters (全部/资产/负债/权益/收入/费用)
- Search by code/name, show disabled toggle
- Columns: 科目编码, 科目名称, 类型, 余额方向, 状态, 操作
- Create modal with AccountPicker, form validation
- Inline name editing, enable/disable toggle
- Delete with ConfirmDialog and error handling
- **QA fix**: Added `level` computation in create payload
- **QA fix**: Added `onError` handler for delete mutation

### 4.2 Route wiring ✅
- `AccountsPage` imported and wired to `/admin/accounts` route

### 4.3 Type fix ✅
- Added `level: number` to `CreateAccountRequest`

---

## Task 5: Integration & QA

**Status**: [x]

### 5.1 Backend verification ✅
- All 5 endpoints implemented, no syntax errors
- Python AST parsing passes

### 5.2 Frontend verification ✅
- TypeScript compilation passes with no errors
- All 3 QA-identified issues fixed and verified

### 5.3 QA Issues Resolved
| Issue | Status |
|---|---|
| AccountTreeNode missing fields | ✅ Fixed — added parent_id, is_cash, aux_types, is_quantity, quantity_unit |
| CreateAccountRequest missing `level` | ✅ Fixed — added level field, computed from parent |
| deleteMutation no error handler | ✅ Fixed — added onError with alert feedback |
