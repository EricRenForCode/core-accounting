# UI Design Prompt — Core Accounting v1

> Senior product designer for Chinese enterprise financial system. Design all pages below using **React 19 + TypeScript + Tailwind v4 + Shadcn/ui + TanStack Router/Query + Zustand + React Hook Form + Zod + Recharts**.

## System Overview

Greenfield internal accounting system (替代浪潮内账). 3 roles × 9 modules × 53+ pages.

- **财务人员:** voucher entry, ledger queries, reports, AI
- **财务经理:** above + audit workflow, period close, AI interpretation
- **管理员:** system admin (accounts/users/roles/periods/logs/backups)

API docs: `document/engineering-spec.md` (all endpoints, schemas, error codes).
UX docs: `document/ux-design.md` (full page wireframes + interactions).

## Global Layout

`AppShell`: Header (Logo + Period Picker + User Avatar) | Sidebar (240px/64px collapsible, search, menu tree, AI entry) | Content (Breadcrumb + main) | StatusBar
Responsive: ≥1024px full sidebar, <1024px hamburger drawer.

## Design Tokens

- **Primary:** #1E3A5F | **Accent:** #3B82F6 | **Success:** #10B981 | **Warning:** #F59E0B | **Error:** #EF4444 | **BG:** #F8FAFC
- **Font:** system Chinese stack; amounts: `JetBrains Mono` monospace, right-aligned, thousand-separators
- **Sizes:** body 14px, headings 16-24px, captions 12px | **Spacing:** 4px base (8/12/16/24/32)

## Shared Patterns

- **DataTable:** sort, filter, paginate (20/50/100), row hover actions, batch checkbox, column visibility/resize, summary footer, skeleton loading, empty state with CTA
- **Forms:** top labels, red asterisk required, blur validation, amounts right-aligned monospace, searchable dropdowns (>20 items)
- **Feedback:** Toast (green 3s success / red error), Modal for delete confirm, Progress bar for long tasks, AI pulse/typewriter for thinking, Top banner for network errors
- **Status Badges:** 草稿(gray) / 已审核(green) / 已记账(blue) / 已冲销(red) / 结账(closed gray)
- **States:** every page handles Default, Loading (skeleton/spinner), Empty (illustration + CTA), Error (inline card + retry)

## Key Design Principles

1. Efficiency: minimize clicks, keyboard shortcuts (Ctrl+S/Enter, Tab/↑↓ for entry navigation)
2. Clarity: monospace amounts, consistent alignment, no distracting animations
3. Error prevention: real-time validation (blur), balance indicator, confirm destructive actions
4. Progressive disclosure: trees for hierarchy, collapse/expand, summaries before details
5. Chinese-first all labels
6. Permission-aware: hide (don't just disable) unauthorized buttons/menus
7. AI transparency: show reasoning, make outputs editable, require confirmation

## Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+S | Save |
| Ctrl+Enter | Save + new |
| Ctrl+N | New voucher |
| Tab/Shift+Tab | Navigate entry columns |
| ↑↓ | Switch entry rows |
| Esc | Close modal |

## Route Tree (all under authenticated layout)

```
/login
/dashboard                      — role-based (3 variants)
/vouchers                       — list
/vouchers/new                   — create
/vouchers/:id                   — detail/edit (slide-out panel)
/vouchers/templates[/:id]       — list/edit
/vouchers/import                — Excel import
/ledgers/trial-balance          — tree table + multi-period comparison
/ledgers/general                — flat account summary
/ledgers/detail/:accountId      — 3-column (期初/本期/期末) + drill-down
/ledgers/multi/:accountId       — dynamic child-account columns
/ledgers/journal                — chronological voucher log
/ledgers/quantity/:accountId    — quantity + price tracking
/auxiliary/:type                — list (departments/individuals/counterparties/projects)
/auxiliary/:type/:id/ledger     — entity-scoped detail ledger
/auxiliary/:type/:id/aging      — aging analysis + bar chart
/reports/balance-sheet          — template-rendered + AI interpretation
/reports/income                 — income statement
/reports/cash-flow              — cash flow (3 sections)
/reports/templates              — template CRUD
/period/carry                   — carry-forward (templates + AI 10 checks + progress)
/period/close                   — close/reopen
/cashier/cash                   — cash journal (running balance)
/cashier/bank                   — bank journal + import flow
/cashier/reconcile              — dual-panel bank reconciliation
/assets[/:id]                   — list / add / edit
/assets/depreciation            — batch + single depreciation
/assets/reports                 — chart + summary
/ai                             — workspace (4 cards + chat panel)
/ai/voucher                     — NL→voucher (editable preview + refine)
/ai/report                      — report interpretation (ratios + risk alerts)
/ai/query                       — NL→SQL→results (multi-turn chat)
/admin/accounts                 — tree editor
/admin/users                    — user CRUD
/admin/roles                    — 23-permission matrix
/admin/periods                  — period CRUD
/admin/params                   — key-value settings
/admin/logs                     — audit log viewer (JSON diff)
/admin/backups                  — backup list + create/restore
```

Route guards: `/admin/*` → role=admin; component-level via `usePermission().can("perm")`.

## Core Page Specs (key interactions only)

### 凭证录入 (VoucherForm) — MOST CRITICAL
- Dual-entry table: AccountPicker (tree dropdown, code/pinyin search) + summary + AuxPicker (conditional on account aux_types) + AmountInput (monospace, XOR per row)
- Real-time BalanceBar: total debit, total credit, difference (red ❌ if unbalanced, green ✅ if balanced)
- Shortcuts: Enter adds row, Tab navigates columns, ↑↓ switches rows, Ctrl+S saves
- Buttons: +新增分录, 从模板加载 (modal picker), 🤖 AI 生成 (see below)
- Validation: blur on all fields, min 2 entries, must balance to save
- API: `POST /vouchers`, `PUT /vouchers/{id}` (draft only)

### 凭证列表 (VoucherList)
- Filter bar: date range, voucher_no, keyword, status dropdown, amount range
- Table: date, voucher_no, summary, debit, credit, status badge. Hover → 查看/编辑/审核/冲销/打印. Checkbox → batch ops.
- Batch bar: appears when ≥1 selected. Export Excel.
- Operations gated by permission: `voucher:audit`, `voucher:post`, `voucher:reverse`

### 科目余额表 (TrialBalance)
- Tree table (expand/collapse), default level 1. "展开全部"/"折叠全部".
- Multi-period toggle → month columns side-by-side.
- Click row → navigate to 三栏明细账.
- Footer totals row. Export Excel.

### 期末结转 (CarryForward)
- Template checklist (全选/全不选). Click row → preview accounts + amounts.
- 🤖 AI 预检: 10 checks (未记账/折旧/暂估/平衡/银行对账...) each ✅/⚠️/❌ + detail.
- "一键执行" disabled if any ❌. Execution → step progress bar, each shows voucher_no.
- Completion modal with summary.

### AI 凭证生成 (AIVoucher)
- Text area (max 500 chars) → "🤖 生成凭证" → pulse loading → editable preview table
- Preview: accounts (dropdown-changeable), amounts (modifiable), real-time balance
- AI notes: matched accounts, auxiliary entities identified
- Suggestion cards with "apply" button
- "修改描述重试" for multi-turn refinement
- "确认并保存" → POST voucher as draft

### AI 工作台 (AIWorkspace)
- Left: 4 function cards (智能凭证/报表解读/期末检查/智能查询) with [开始] buttons
- Right: chat panel with results table, expandable SQL, multi-turn conversation
- Global floating 💬 button (bottom-right) opens overlay

### AI NL Query
- Chat input → LLM generates SQL (shown expandable) → runs read-only → result table
- Multi-turn follow-up within conversation
- "解释SQL" button, execution time shown

### 资产负债表 (BalanceSheet)
- Template dropdown + period picker + "生成" button
- Hierarchical sections (▶ toggle), bold subtotals, separator lines
- Collapsible 🤖 AI 解读 panel: YoY/MoM changes, ratios, risk alerts (>20% flagged)
- Export Excel/PDF

### 银行对账 (BankReconcile)
- Dual-panel: left=bank statements, right=system entries
- Select items on both sides → "对账" to match
- Unmatched items highlighted

### 辅助核算 (Auxiliary)
- 4 tabs: 部门/个人/单位/项目 → same generic table (code, name, status)
- Detail ledger: entities → voucher entries scoped to that entity
- Aging: buckets (0-30/31-60/61-90/91-180/181-365/365+ days) + bar chart

### 固定资产 (Assets)
- List: code, name, category, amounts, depreciation, net_value, status badge
- Form: depreciation_method dropdown (直线法/双倍余额递减法/年数总和法), auto-calc monthly_depreciation
- Batch depreciation: period-selector → executes all active assets

### 权限管理 (Roles)
- Click role → 23-toggle matrix (checkboxes for each permission)
- Save button

### 审计日志 (AuditLogs)
- Table: timestamp, user, action, resource, IP
- Expand row → old_values/new_values JSON diff
- Filters: user, action, date, resource type. Export CSV.

## Existing Built Components (reuse, don't recreate)

`AppShell`, `Header`, `Sidebar`, `Breadcrumb`, `DataTable`, `DataTablePagination`, `DataTableToolbar`, `AccountPicker`, `AuxPicker`, `AmountInput`, `BalanceBar`, `StatusBadge`, `EmptyState`, `ErrorCard`, `Skeleton`, `Toast`, `ConfirmDialog`
Hooks: `useAuth`, `useCurrentPeriod`, `usePermission`
Stores: `appStore` (sidebar, period), `userStore` (user, permissions)
Lib: `api.ts` (Axios+JWT), `constants.ts`, `utils.ts`

## Design Checklist (42 items)

- [ ] Login
- [ ] Dashboard (3 role variants)
- [ ] Voucher List, Voucher Form, Voucher Detail, Template List, Template Form, Import
- [ ] Trial Balance, General Ledger, Detail Ledger, Multi-Column Ledger, Journal, Quantity Ledger
- [ ] Aux List (4 tabs), Aux Ledger, Aging Analysis
- [ ] Balance Sheet, Income Statement, Cash Flow, Report Templates
- [ ] Carry Forward, Period Close/Reopen
- [ ] Cash Journal, Bank Journal, Bank Reconciliation
- [ ] Asset List, Asset Form, Depreciation, Asset Reports
- [ ] AI Workspace, AI Voucher Gen, AI Report Interpreter, AI Period Checker, AI NL Query
- [ ] Account Mgmt, User Mgmt, Role Mgmt, Period Mgmt, Params, Audit Logs, Backups

For each: default / loading / empty / error states, interactions, API endpoints, permission gating.

---

*Generated from design.md + ux-design.md + engineering-spec.md v0.2 | 2026-06-14*
