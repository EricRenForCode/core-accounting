import { createRootRoute, createRoute } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import UsersPage from '@/features/admin/UsersPage'
import RolesPage from '@/features/admin/RolesPage'

// ─── Placeholder pages ──────────────────────────────

function DashboardPage() {
  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">仪表盘</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {['草稿凭证', '待审核', '已记账', '本月凭证'].map((label) => (
          <div key={label} className="rounded-lg border bg-card p-4">
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold mt-1">—</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm rounded-lg border bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-center text-primary mb-6">
          <span className="text-accent">Core</span>Accounting
        </h1>
        <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
          <div>
            <label className="block text-sm font-medium mb-1">用户名</label>
            <input
              type="text"
              className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              placeholder="请输入用户名"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">密码</label>
            <input
              type="password"
              className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              placeholder="请输入密码"
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-md bg-accent py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors"
          >
            登录
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

function VoucherListPage() { return <PlaceholderPage title="凭证列表" /> }
function VoucherNewPage() { return <PlaceholderPage title="录入凭证" /> }
function VoucherTemplatePage() { return <PlaceholderPage title="凭证模板" /> }

// ─── Root Route ─────────────────────────────────────

const rootRoute = createRootRoute({
  component: AppShell,
})

// ─── Public Routes ──────────────────────────────────

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
})

// ─── Dashboard ──────────────────────────────────────

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dashboard',
  component: DashboardPage,
})

// ─── Vouchers ───────────────────────────────────────

const vouchersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/vouchers',
  component: VoucherListPage,
})

const voucherNewRoute = createRoute({
  getParentRoute: () => vouchersRoute,
  path: '/new',
  component: VoucherNewPage,
})

const voucherTemplatesRoute = createRoute({
  getParentRoute: () => vouchersRoute,
  path: '/templates',
  component: VoucherTemplatePage,
})

// ─── Ledgers ────────────────────────────────────────

const ledgersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/ledgers',
  component: () => <PlaceholderPage title="账表查询" />,
})

const trialBalanceRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/trial-balance',
  component: () => <PlaceholderPage title="科目余额表" />,
})

const generalLedgerRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/general',
  component: () => <PlaceholderPage title="总账" />,
})

const detailLedgerRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/detail',
  component: () => <PlaceholderPage title="三栏明细账" />,
})

const multiColumnRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/multi-column',
  component: () => <PlaceholderPage title="多栏明细账" />,
})

const journalRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/journal',
  component: () => <PlaceholderPage title="序时账" />,
})

const quantityLedgerRoute = createRoute({
  getParentRoute: () => ledgersRoute,
  path: '/quantity',
  component: () => <PlaceholderPage title="数量金额账" />,
})

// ─── Auxiliary ──────────────────────────────────────

const auxiliaryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/auxiliary',
  component: () => <PlaceholderPage title="辅助核算" />,
})

// ─── Reports ────────────────────────────────────────

const reportsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/reports',
  component: () => <PlaceholderPage title="财务报表" />,
})

const balanceSheetRoute = createRoute({
  getParentRoute: () => reportsRoute,
  path: '/balance-sheet',
  component: () => <PlaceholderPage title="资产负债表" />,
})

const incomeRoute = createRoute({
  getParentRoute: () => reportsRoute,
  path: '/income',
  component: () => <PlaceholderPage title="利润表" />,
})

const cashFlowRoute = createRoute({
  getParentRoute: () => reportsRoute,
  path: '/cash-flow',
  component: () => <PlaceholderPage title="现金流量表" />,
})

// ─── Period ─────────────────────────────────────────

const periodRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/period',
  component: () => <PlaceholderPage title="期末处理" />,
})

const periodCloseRoute = createRoute({
  getParentRoute: () => periodRoute,
  path: '/close',
  component: () => <PlaceholderPage title="结账" />,
})

const carryForwardRoute = createRoute({
  getParentRoute: () => periodRoute,
  path: '/carry-forward',
  component: () => <PlaceholderPage title="期末结转" />,
})

// ─── Cashier ────────────────────────────────────────

const cashierRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/cashier',
  component: () => <PlaceholderPage title="出纳管理" />,
})

const cashJournalRoute = createRoute({
  getParentRoute: () => cashierRoute,
  path: '/cash',
  component: () => <PlaceholderPage title="现金日记账" />,
})

const bankJournalRoute = createRoute({
  getParentRoute: () => cashierRoute,
  path: '/bank',
  component: () => <PlaceholderPage title="银行日记账" />,
})

const bankReconcileRoute = createRoute({
  getParentRoute: () => cashierRoute,
  path: '/reconcile',
  component: () => <PlaceholderPage title="银行对账" />,
})

// ─── Assets ─────────────────────────────────────────

const assetsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/assets',
  component: () => <PlaceholderPage title="固定资产" />,
})

const assetListRoute = createRoute({
  getParentRoute: () => assetsRoute,
  path: '/list',
  component: () => <PlaceholderPage title="资产列表" />,
})

const assetReportRoute = createRoute({
  getParentRoute: () => assetsRoute,
  path: '/reports',
  component: () => <PlaceholderPage title="资产报表" />,
})

// ─── AI ─────────────────────────────────────────────

const aiRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/ai',
  component: () => <PlaceholderPage title="AI 工作台" />,
})

const aiVoucherRoute = createRoute({
  getParentRoute: () => aiRoute,
  path: '/voucher',
  component: () => <PlaceholderPage title="智能凭证" />,
})

const aiReportRoute = createRoute({
  getParentRoute: () => aiRoute,
  path: '/report',
  component: () => <PlaceholderPage title="报表解读" />,
})

const aiQueryRoute = createRoute({
  getParentRoute: () => aiRoute,
  path: '/query',
  component: () => <PlaceholderPage title="自然语言查询" />,
})

// ─── Admin ──────────────────────────────────────────

const adminRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin',
  component: () => <PlaceholderPage title="系统管理" />,
})

const adminAccountsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/accounts',
  component: () => <PlaceholderPage title="科目管理" />,
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
  component: () => <PlaceholderPage title="会计期间" />,
})

const adminParamsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/params',
  component: () => <PlaceholderPage title="系统参数" />,
})

const adminAuditRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/audit-logs',
  component: () => <PlaceholderPage title="审计日志" />,
})

const adminBackupRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/backup',
  component: () => <PlaceholderPage title="数据备份" />,
})

// ─── Index (redirect to dashboard) ──────────────────

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: DashboardPage,
})

// ─── Route Tree ─────────────────────────────────────

export const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  dashboardRoute,
  vouchersRoute.addChildren([
    voucherNewRoute,
    voucherTemplatesRoute,
  ]),
  ledgersRoute.addChildren([
    trialBalanceRoute,
    generalLedgerRoute,
    detailLedgerRoute,
    multiColumnRoute,
    journalRoute,
    quantityLedgerRoute,
  ]),
  auxiliaryRoute,
  reportsRoute.addChildren([
    balanceSheetRoute,
    incomeRoute,
    cashFlowRoute,
  ]),
  periodRoute.addChildren([
    periodCloseRoute,
    carryForwardRoute,
  ]),
  cashierRoute.addChildren([
    cashJournalRoute,
    bankJournalRoute,
    bankReconcileRoute,
  ]),
  assetsRoute.addChildren([
    assetListRoute,
    assetReportRoute,
  ]),
  aiRoute.addChildren([
    aiVoucherRoute,
    aiReportRoute,
    aiQueryRoute,
  ]),
  adminRoute.addChildren([
    adminAccountsRoute,
    adminUsersRoute,
    adminRolesRoute,
    adminPeriodsRoute,
    adminParamsRoute,
    adminAuditRoute,
    adminBackupRoute,
  ]),
])
