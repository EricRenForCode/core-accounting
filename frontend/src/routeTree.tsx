import { useState, type FormEvent } from 'react'
import { createRootRoute, createRoute, Outlet, useNavigate } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import UsersPage from '@/features/admin/UsersPage'
import RolesPage from '@/features/admin/RolesPage'
import AccountsPage from '@/features/admin/AccountsPage'
import DashboardPage from '@/features/dashboard/DashboardPage'
import PeriodManage from '@/features/admin/PeriodManage'
import ParamsManage from '@/features/admin/ParamsManage'
import AuditLogViewer from '@/features/admin/AuditLogViewer'
import VoucherForm from '@/features/vouchers/VoucherForm'
import VoucherList from '@/features/vouchers/VoucherList'
import VoucherDetail from '@/features/vouchers/VoucherDetail'
import VoucherTemplateList from '@/features/vouchers/VoucherTemplateList'
import VoucherTemplateForm from '@/features/vouchers/VoucherTemplateForm'
import TrialBalance from '@/features/ledgers/TrialBalance'
import GeneralLedger from '@/features/ledgers/GeneralLedger'
import DetailLedger from '@/features/ledgers/DetailLedger'
import JournalLedger from '@/features/ledgers/JournalLedger'
import MultiColumnLedger from '@/features/ledgers/MultiColumnLedger'
import QuantityLedger from '@/features/ledgers/QuantityLedger'
import AuxList from '@/features/auxiliary/AuxList'
import CashJournal from '@/features/cashier/CashJournal'
import BankJournal from '@/features/cashier/BankJournal'
import BankReconcile from '@/features/cashier/BankReconcile'
import AssetList from '@/features/assets/AssetList'
import AssetReports from '@/features/assets/AssetReports'
import BalanceSheetPage from '@/features/reports/BalanceSheet'
import IncomeStatementPage from '@/features/reports/IncomeStatement'
import CashFlowStatementPage from '@/features/reports/CashFlowStatement'
import ReportTemplateManagerPage from '@/features/reports/ReportTemplateManager'
import CarryForwardPage from '@/features/period/CarryForward'
import AINLQueryPage from '@/features/ai/AINLQuery'
import AIReportInterpreterPage from '@/features/ai/AIReportInterpreter'
import AIVoucherGeneratorPage from '@/features/ai/AIVoucherGenerator'
import AIWorkspacePage from '@/features/ai/AIWorkspace'
import PeriodClosePage from '@/features/period/PeriodClose'
import OpeningBalancesPage from '@/features/period/OpeningBalances'
import api from '@/lib/api'
import { useUserStore } from '@/stores/userStore'
import type { Permission } from '@/lib/constants'

// ─── Placeholder pages ──────────────────────────────

function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const setUser = useUserStore((s) => s.setUser)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')

    if (!username.trim() || !password.trim()) {
      setError('请输入用户名和密码')
      return
    }

    setLoading(true)
    try {
      const { data } = await api.post('/auth/login', { username, password })

      localStorage.setItem('access_token', data.tokens.access_token)
      localStorage.setItem('refresh_token', data.tokens.refresh_token)

      setUser({
        id: data.user.id,
        username: data.user.username,
        display_name: data.user.display_name,
        role_id: '',
        role_name: data.user.role,
        permissions: data.user.permissions as Permission[],
        is_enabled: data.user.is_enabled,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      navigate({ to: '/dashboard' })
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || '登录失败，请重试'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm rounded-lg border bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-center text-primary mb-6">
          <span className="text-accent">Core</span>Accounting
        </h1>
        <form className="space-y-4" onSubmit={handleSubmit}>
          {error && (
            <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-600">
              {error}
            </div>
          )}
          <div>
            <label className="block text-sm font-medium mb-1">用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              placeholder="请输入用户名"
              autoComplete="username"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              placeholder="请输入密码"
              autoComplete="current-password"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-accent py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </form>
      </div>
    </div>
  )
}

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">{title}</h2>
      <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
        <p className="text-lg">🚧 {title} — 功能开发中</p>
        <p className="text-sm mt-2">此页面将在后续 Phase 中实现</p>
      </div>
    </div>
  )
}

function VoucherNewPage() { return <VoucherForm /> }

// ─── Root Route (no layout — pure outlet) ──────────

const rootRoute = createRootRoute({
  component: () => <Outlet />,
})

// ─── Public Routes (outside AppShell) ───────────────

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
})

// ─── Authenticated Layout (AppShell wrapper) ────────

const authenticatedRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'authenticated',
  component: AppShell,
})

// ─── Dashboard ──────────────────────────────────────

const dashboardRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/dashboard',
  component: DashboardPage,
})

// ─── Vouchers ───────────────────────────────────────

const vouchersRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/vouchers',
  component: () => <Outlet />,
})

const vouchersIndexRoute = createRoute({
  getParentRoute: () => vouchersRoute,
  path: '/',
  component: VoucherList,
})

const voucherNewRoute = createRoute({
  getParentRoute: () => vouchersRoute,
  path: '/new',
  component: VoucherNewPage,
})

const voucherTemplatesRoute = createRoute({
  getParentRoute: () => vouchersRoute,
  path: '/templates',
  component: VoucherTemplateList,
})

const voucherTemplateNewRoute = createRoute({
  getParentRoute: () => vouchersRoute,
  path: '/templates/new',
  component: VoucherTemplateForm,
})

const voucherTemplateEditRoute = createRoute({
  getParentRoute: () => vouchersRoute,
  path: '/templates/$templateId',
  component: VoucherTemplateForm,
})

const voucherDetailRoute = createRoute({
  getParentRoute: () => vouchersRoute,
  path: '/$voucherId',
  component: VoucherDetail,
})

// ─── Ledgers ────────────────────────────────────────

const ledgersRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/ledgers',
  component: () => <Outlet />,
})

const ledgersIndexRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/',
  component: () => <PlaceholderPage title="账表查询" />,
})

const trialBalanceRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/trial-balance',
  component: TrialBalance,
})

const generalLedgerRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/general',
  component: GeneralLedger,
})

const detailLedgerRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/detail',
  component: DetailLedger,
})

const multiColumnRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/multi-column',
  component: MultiColumnLedger,
})

const journalRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/journal',
  component: JournalLedger,
})

const quantityLedgerRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/quantity',
  component: QuantityLedger,
})

// ─── Auxiliary ──────────────────────────────────────

const auxiliaryRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/auxiliary',
  component: AuxList,
})

// ─── Reports ────────────────────────────────────────

const reportsRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/reports',
  component: () => <Outlet />,
})

const reportsIndexRoute = createRoute({
  getParentRoute: () => reportsRoute,
  path: '/',
  component: ReportTemplateManagerPage,
})

const balanceSheetRoute = createRoute({
  getParentRoute: () => reportsRoute,
  path: '/balance-sheet',
  component: BalanceSheetPage,
})

const incomeRoute = createRoute({
  getParentRoute: () => reportsRoute,
  path: '/income',
  component: IncomeStatementPage,
})

const cashFlowRoute = createRoute({
  getParentRoute: () => reportsRoute,
  path: '/cash-flow',
  component: CashFlowStatementPage,
})

// ─── Period ─────────────────────────────────────────

const periodRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/period',
  component: () => <Outlet />,
})

const periodIndexRoute = createRoute({
  getParentRoute: () => periodRoute,
  path: '/',
  component: PeriodClosePage,
})

const periodCloseRoute = createRoute({
  getParentRoute: () => periodRoute,
  path: '/close',
  component: PeriodClosePage,
})

const carryForwardRoute = createRoute({
  getParentRoute: () => periodRoute,
  path: '/carry-forward',
  component: CarryForwardPage,
})

const openingBalancesRoute = createRoute({
  getParentRoute: () => periodRoute,
  path: '/opening-balances',
  component: OpeningBalancesPage,
})

// ─── Cashier ────────────────────────────────────────

const cashierRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/cashier',
  component: () => <Outlet />,
})

const cashierIndexRoute = createRoute({
  getParentRoute: () => cashierRoute,
  path: '/',
  component: CashJournal,
})

const cashJournalRoute = createRoute({
  getParentRoute: () => cashierRoute,
  path: '/cash',
  component: CashJournal,
})

const bankJournalRoute = createRoute({
  getParentRoute: () => cashierRoute,
  path: '/bank',
  component: BankJournal,
})

const bankReconcileRoute = createRoute({
  getParentRoute: () => cashierRoute,
  path: '/reconcile',
  component: BankReconcile,
})

// ─── Assets ─────────────────────────────────────────

const assetsRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/assets',
  component: () => <Outlet />,
})

const assetsIndexRoute = createRoute({
  getParentRoute: () => assetsRoute,
  path: '/',
  component: AssetList,
})

const assetListRoute = createRoute({
  getParentRoute: () => assetsRoute,
  path: '/list',
  component: AssetList,
})

const assetReportRoute = createRoute({
  getParentRoute: () => assetsRoute,
  path: '/reports',
  component: AssetReports,
})

// ─── AI ─────────────────────────────────────────────

const aiRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/ai',
  component: () => <Outlet />,
})

const aiIndexRoute = createRoute({
  getParentRoute: () => aiRoute,
  path: '/',
  component: AIWorkspacePage,
})

const aiVoucherRoute = createRoute({
  getParentRoute: () => aiRoute,
  path: '/voucher',
  component: AIVoucherGeneratorPage,
})

const aiReportRoute = createRoute({
  getParentRoute: () => aiRoute,
  path: '/report',
  component: AIReportInterpreterPage,
})

const aiQueryRoute = createRoute({
  getParentRoute: () => aiRoute,
  path: '/query',
  component: AINLQueryPage,
})

// ─── Admin ──────────────────────────────────────────

const adminRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/admin',
  component: () => <Outlet />,
})

const adminIndexRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/',
  component: () => <PlaceholderPage title="系统管理" />,
})

const adminAccountsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/accounts',
  component: AccountsPage,
})

const adminUsersRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/users',
  component: UsersPage,
})

const adminRolesRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/roles',
  component: RolesPage,
})

const adminPeriodsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/periods',
  component: PeriodManage,
})

const adminParamsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/params',
  component: ParamsManage,
})

const adminAuditRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/audit-logs',
  component: AuditLogViewer,
})

const adminBackupRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/backup',
  component: () => <PlaceholderPage title="数据备份" />,
})

// ─── Index (redirect to dashboard) ──────────────────

const indexRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: '/',
  component: DashboardPage,
})

// ─── Route Tree ─────────────────────────────────────

export const routeTree = rootRoute.addChildren([
  loginRoute,
  authenticatedRoute.addChildren([
  indexRoute,
  dashboardRoute,
  vouchersRoute.addChildren([
    vouchersIndexRoute,
    voucherNewRoute,
    voucherTemplatesRoute,
    voucherTemplateNewRoute,
    voucherTemplateEditRoute,
    voucherDetailRoute,
  ]),
  ledgersRoute.addChildren([
    ledgersIndexRoute,
    trialBalanceRoute,
    generalLedgerRoute,
    detailLedgerRoute,
    multiColumnRoute,
    journalRoute,
    quantityLedgerRoute,
  ]),
  auxiliaryRoute,
  reportsRoute.addChildren([
    reportsIndexRoute,
    balanceSheetRoute,
    incomeRoute,
    cashFlowRoute,
  ]),
  periodRoute.addChildren([
    periodIndexRoute,
    periodCloseRoute,
    carryForwardRoute,
    openingBalancesRoute,
  ]),
  cashierRoute.addChildren([
    cashierIndexRoute,
    cashJournalRoute,
    bankJournalRoute,
    bankReconcileRoute,
  ]),
  assetsRoute.addChildren([
    assetsIndexRoute,
    assetListRoute,
    assetReportRoute,
  ]),
  aiRoute.addChildren([
    aiIndexRoute,
    aiVoucherRoute,
    aiReportRoute,
    aiQueryRoute,
  ]),
  adminRoute.addChildren([
    adminIndexRoute,
    adminAccountsRoute,
    adminUsersRoute,
    adminRolesRoute,
    adminPeriodsRoute,
    adminParamsRoute,
    adminAuditRoute,
    adminBackupRoute,
  ]),
  ]),
])
