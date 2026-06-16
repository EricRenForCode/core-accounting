# Phase 1: UI Skeleton Prompt — Core Accounting v1

> Role: Senior frontend designer. Build the app shell and foundation first.
> Stack: React 19 + TypeScript + Tailwind v4 + Shadcn/ui + TanStack Router/Query + Zustand + React Hook Form + Zod

## What to Build — App Skeleton

1. **Login page** — username/password, login, error handling
2. **Global layout shell** — every authenticated page uses this
3. **Route tree** — all routes defined with role-based guards
4. **Shared component library** — DataTable, forms, feedback, status badges
5. **Design system** — tokens applied globally

Do NOT build any feature pages yet (vouchers, ledgers, reports, etc.). Those come in later batches.

---

## 1. Login Page

```
┌──────────────────────────────────┐
│          Core Accounting         │
│                                  │
│   ┌────────────────────────┐    │
│   │  用户名: [________]     │    │
│   │  密码:   [________]     │    │
│   │  [ 登录 ]               │    │
│   └────────────────────────┘    │
│                                  │
│  错误提示（红色）                │
└──────────────────────────────────┘
```

- Username + password + submit
- Loading state on submit
- Error: red text below form (401, network error)
- On success: store token, redirect to `/dashboard`
- Public route (no auth required)

---

## 2. Global Layout Shell (AppShell)

```
┌──────────────────────────────────────────────────────┐
│  HEADER: Logo | 当前期间: 2026-06 | 用户头像 · 角色  │
├──────────┬───────────────────────────────────────────┤
│ SIDEBAR  │  BREADCRUMB (auto from route)             │
│          │  ───────────────────────────              │
│          │  CONTENT AREA (route outlet)              │
│          │                                          │
├──────────┴───────────────────────────────────────────┤
│  STATUS BAR: online | last backup | version          │
└──────────────────────────────────────────────────────┘
```

### Header
- Left: App logo/name
- Center-right: current period selector (dropdown, from `useCurrentPeriod`)
- Right: user avatar + display_name + role badge, click → dropdown (profile, logout)

### Sidebar
- Width: 240px expanded / 64px collapsed
- Collapse toggle button (<< / >>)
- Top: search input (filter menu items by pinyin/Chinese)
- Menu tree: multi-level, expandable sub-items, icons
- Active item: left blue bar + light blue background
- Bottom: AI assistant shortcut (💬) + collapse button
- **Role-based menu filtering:**
  - finance_staff: all except 系统管理
  - finance_manager: all except 系统管理, + audit badge on 凭证列表
  - admin: 系统管理 on TOP, all other modules below

### Breadcrumb
- Auto-generated from route path, e.g. "凭证管理 > 录入凭证"

### Status Bar
- Left: connection status indicator
- Center: last backup time
- Right: version number
- Thin, subtle, non-distracting

### Responsive
- ≥1024px: full sidebar
- <1024px: sidebar hidden, hamburger in header opens drawer overlay

---

## 3. Route Tree

All routes defined as TanStack Router file-based or code-based routes:

```
/login                    — public

(auth layout):
  /                       — redirect → /dashboard
  /dashboard

  /vouchers
  /vouchers/new
  /vouchers/$id
  /vouchers/templates
  /vouchers/templates/new
  /vouchers/templates/$id
  /vouchers/import

  /ledgers/trial-balance
  /ledgers/general
  /ledgers/detail/$accountId
  /ledgers/multi/$accountId
  /ledgers/journal
  /ledgers/quantity/$accountId

  /auxiliary/$type
  /auxiliary/$type/$id/ledger
  /auxiliary/$type/$id/aging

  /reports/balance-sheet
  /reports/income
  /reports/cash-flow
  /reports/templates

  /period/carry
  /period/close

  /cashier/cash
  /cashier/bank
  /cashier/reconcile

  /assets
  /assets/new
  /assets/$id
  /assets/depreciation
  /assets/reports

  /ai
  /ai/voucher
  /ai/report
  /ai/query

  /admin/accounts
  /admin/users
  /admin/roles
  /admin/periods
  /admin/params
  /admin/logs
  /admin/backups
```

### Route Guards
- `beforeLoad` on auth layout: check `useAuth().isAuthenticated` → else redirect `/login`
- `beforeLoad` on `/admin/*`: check `role === 'admin'` → else redirect `/dashboard` with toast
- Placeholder pages for ALL routes (empty state: "页面建设中")

---

## 4. Shared Components

Build these ONCE, reuse everywhere:

### DataTable `<DataTable<T>>`
- TanStack Table with generic type `<T>`
- Props: columns, data, total, page, pageSize, onPaginationChange, onSortChange, isLoading, toolbar, rowActions, onRowClick, selectable, selectedRows, onSelectionChange, footer
- Features: sorting (click header), pagination (page numbers + size selector + "共 X 条"), checkbox selection, hover row actions, summary footer row
- States: loading → skeleton rows; empty → EmptyState
- Column resize: drag borders
- Column visibility: gear icon dropdown

### DataTablePagination
- `< 1 2 3 ... 7 >` page navigation + page size selector (20 / 50 / 100) + "共 128 条"

### DataTableToolbar
- Filter bar slot: date pickers, dropdowns, text inputs, query/reset buttons
- Export button

### Form Components
- **AccountPicker:** tree dropdown, search by code/pinyin, keyboard ↑↓ Enter
- **AuxPicker:** dropdown by aux type (personal/department/counterparty/project), searchable
- **AmountInput:** right-aligned, JetBrains Mono, thousand-separator on blur, controlled number value
- **PeriodPicker:** month/year picker showing current period
- Form pattern: React Hook Form + Zod schema, top-aligned labels, red asterisk for required, blur + submit validation, red border + text on error

### Feedback
- **BalanceBar:** shows totalDebit, totalCredit, difference. Green ✅ if balanced, red ❌ if not.
- **StatusBadge:** color-coded tag (草稿=gray, 已审核=green, 已记账=blue, 已冲销=red)
- **Toast:** top-right, auto-dismiss (3s success green, error red with message)
- **ConfirmDialog:** modal, title + body + 取消 + 确认删除 (red) buttons
- **EmptyState:** centered icon + message + CTA button
- **ErrorCard:** inline card with error message + retry button
- **Skeleton:** gray placeholder bars with shimmer animation

### AI Loading States
- **PulseAnimation:** for AI thinking (subtle glow pulse on card/button)
- **TypewriterEffect:** character-by-character text reveal for AI responses

---

## 5. Design Tokens (Tailwind Config)

### Colors
```
primary:    #1E3A5F (deep blue)
accent:     #3B82F6 (blue)
success:    #10B981 (green)
warning:    #F59E0B (orange)
destructive:#EF4444 (red)
background: #F8FAFC (light gray)
card:       #FFFFFF
border:     #E2E8F0
text-primary:   #1E293B
text-secondary: #64748B
sidebar-bg:     #0F1D32 (dark navy)
sidebar-text:   #94A3B8
```

### Typography
- Font: `"PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", sans-serif`
- Mono (amounts): `"JetBrains Mono", "SF Mono", monospace`
- Sizes: body 14px, h4 16px, h3 18px, h2 20px, h1 24px, caption 12px
- Amounts: ALWAYS monospace + right-aligned + thousand-separator

### Spacing & Radius
- Base: 4px. Card padding: p-4 (16px). Card gap: gap-4.
- Border radius: rounded-lg for cards, rounded-md for inputs/buttons

---

## 6. Auth & State Setup

### API Layer (`lib/api.ts`)
- Axios instance, baseURL from env
- Request interceptor: attach `Authorization: Bearer <token>`
- Response interceptor: on 401 → try refresh token → retry; if refresh fails → logout → redirect `/login`
- Unified error transform to `{ code, message, detail }`

### Zustand Stores
```
appStore: { sidebarOpen, toggleSidebar, currentPeriod }
userStore: { user, permissions, token, setUser, logout, can(permission) }
```

### TanStack Query
- QueryClient with defaults: staleTime 30s, retry 1
- Wrap app in `<QueryClientProvider>`

### Hooks
- `useAuth()`: login, logout, isAuthenticated, user, isLoading
- `useCurrentPeriod()`: { id, year, month }
- `usePermission()`: `can("voucher:audit")` → boolean

### Types
Ensure these are in `src/types/`:
- `api.ts`: PaginatedResponse<T>, ApiError
- `user.ts`: User, Role, Permission
- `voucher.ts`: Voucher, VoucherEntry, VoucherTemplate, CreateVoucherRequest
- `account.ts`: Account, AccountTree
- `report.ts`: TrialBalance, BalanceSheet, IncomeStatement, CashFlowStatement
- `auxiliary.ts`: Department, Individual, Counterparty, Project
- `asset.ts`: FixedAsset, DepreciationRecord
- `period.ts`: Period, CarryForwardTemplate, CarryForwardResult
- `ai.ts`: AIVoucherResponse, AIQueryResponse, AICheckResult

### Constants (`lib/constants.ts`)
- Roles enum, status enums, permission matrix, error codes map, aux types

---

## 7. Deliverable

Build complete, working frontend skeleton with:
- [x] `pnpm dev` → login page renders
- [x] Login flow works (stores token, redirects)
- [x] Authenticated shell renders: Header + Sidebar + Breadcrumb + Content area
- [x] All 38 routes defined with placeholder pages
- [x] Route guards working (unauthenticated → /login, non-admin → /admin blocked)
- [x] Sidebar role filtering works
- [x] Sidebar collapse/expand works
- [x] All shared components built and exported from `src/components/`
- [x] Design tokens applied globally via Tailwind config
- [x] No feature page logic — only placeholders/empty states

---

*Phase 1 of N. Next batch: 凭证管理 module pages.*
