import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  FileText,
  FileClock,
  BookCheck,
  Files,
  Scale,
  Activity,
  PlusCircle,
  ListChecks,
  CalendarCheck,
} from 'lucide-react'
import api from '@/lib/api'
import { useUserStore } from '@/stores/userStore'

interface VoucherCounts {
  draft: number
  audited: number
  posted: number
  reversed: number
  total: number
}

interface TrialBalance {
  total_debit: number | string
  total_credit: number | string
  is_balanced: boolean
}

interface ActivityItem {
  action: string
  resource_type: string
  resource_id: string | null
  user: string | null
  created_at: string | null
}

interface DashboardSummary {
  period: { id: string; year: number; month: number; status: string } | null
  voucher_counts: VoucherCounts
  trial_balance: TrialBalance
  recent_activity: ActivityItem[]
}

function fmtMoney(n: number | string): string {
  const val = typeof n === 'string' ? parseFloat(n) : n
  return (val || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

const ACTION_LABELS: Record<string, string> = {
  INSERT: '新增',
  UPDATE: '修改',
  DELETE: '删除',
  create: '新增',
  update: '修改',
  delete: '删除',
  audit: '审核',
  post: '记账',
  reverse: '冲销',
  close: '结账',
  reopen: '反结账',
}

const RESOURCE_LABELS: Record<string, string> = {
  voucher: '凭证',
  account: '科目',
  period: '会计期间',
  user: '用户',
  role: '角色',
  fixed_asset: '固定资产',
  auxiliary: '辅助核算',
}

function relativeTime(iso: string | null): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  const diff = Date.now() - then
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} 小时前`
  const days = Math.floor(hrs / 24)
  if (days < 30) return `${days} 天前`
  return new Date(iso).toLocaleDateString('zh-CN')
}

const STAT_CARDS = [
  { key: 'draft', label: '草稿凭证', icon: FileText, color: 'text-gray-500', bg: 'bg-gray-100' },
  { key: 'audited', label: '待记账（已审核）', icon: FileClock, color: 'text-amber-600', bg: 'bg-amber-100' },
  { key: 'posted', label: '已记账', icon: BookCheck, color: 'text-green-600', bg: 'bg-green-100' },
  { key: 'total', label: '本期凭证合计', icon: Files, color: 'text-accent', bg: 'bg-accent/10' },
] as const

const QUICK_ACTIONS = [
  { to: '/vouchers/new', label: '录入凭证', icon: PlusCircle },
  { to: '/vouchers', label: '凭证列表', icon: ListChecks },
  { to: '/ledgers/trial-balance', label: '试算平衡', icon: Scale },
  { to: '/period/close', label: '期末结账', icon: CalendarCheck },
] as const

export default function DashboardPage() {
  const user = useUserStore((s) => s.user)

  const { data, isLoading, isError } = useQuery<DashboardSummary>({
    queryKey: ['dashboard-summary'],
    queryFn: async () => {
      const { data } = await api.get<DashboardSummary>('/dashboard/summary')
      return data
    },
  })

  const counts = data?.voucher_counts
  const tb = data?.trial_balance

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-2xl font-bold">
            {user?.display_name ? `欢迎回来，${user.display_name}` : '仪表盘'}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.period
              ? `当前期间 ${data.period.year}年${data.period.month}月`
              : isLoading
                ? '加载中...'
                : '暂无会计期间'}
            {data?.period && (
              <span
                className={`ml-2 inline-block rounded px-1.5 py-0.5 text-xs ${
                  data.period.status === 'open'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-200 text-gray-600'
                }`}
              >
                {data.period.status === 'open' ? '进行中' : '已结账'}
              </span>
            )}
          </p>
        </div>
      </div>

      {isError && (
        <div className="rounded-lg border bg-red-50 p-4 text-sm text-red-600">
          加载仪表盘数据失败，请稍后重试。
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {STAT_CARDS.map(({ key, label, icon: Icon, color, bg }) => (
          <div key={key} className="rounded-lg border bg-card p-4 flex items-center gap-4">
            <div className={`rounded-lg p-2.5 ${bg}`}>
              <Icon size={22} className={color} />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{label}</p>
              <p className="text-2xl font-bold mt-0.5">
                {isLoading ? '—' : (counts?.[key] ?? 0)}
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trial balance status */}
        <div className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Scale size={18} className="text-accent" />
            <h3 className="font-semibold">本期试算平衡</h3>
          </div>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">加载中...</p>
          ) : (
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">本期借方合计</span>
                <span className="font-mono font-medium">{fmtMoney(tb?.total_debit ?? 0)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">本期贷方合计</span>
                <span className="font-mono font-medium">{fmtMoney(tb?.total_credit ?? 0)}</span>
              </div>
              <div className="border-t pt-3 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">平衡状态</span>
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
                    tb?.is_balanced
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}
                >
                  {tb?.is_balanced ? '✓ 借贷平衡' : '✗ 借贷不平'}
                </span>
              </div>
              <Link
                to="/ledgers/trial-balance"
                className="block text-center text-sm text-accent hover:underline mt-2"
              >
                查看试算平衡表 →
              </Link>
            </div>
          )}
        </div>

        {/* Quick actions */}
        <div className="rounded-lg border bg-card p-5">
          <h3 className="font-semibold mb-4">快捷操作</h3>
          <div className="grid grid-cols-2 gap-3">
            {QUICK_ACTIONS.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                className="flex flex-col items-center gap-2 rounded-lg border p-4 text-sm hover:bg-gray-50 hover:border-accent transition-colors"
              >
                <Icon size={20} className="text-accent" />
                <span>{label}</span>
              </Link>
            ))}
          </div>
        </div>

        {/* Recent activity */}
        <div className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={18} className="text-accent" />
            <h3 className="font-semibold">最近动态</h3>
          </div>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">加载中...</p>
          ) : data && data.recent_activity.length > 0 ? (
            <ul className="space-y-3">
              {data.recent_activity.map((item, idx) => (
                <li key={idx} className="flex items-start justify-between gap-2 text-sm">
                  <span className="text-foreground">
                    <span className="text-muted-foreground">{item.user || '系统'}</span>{' '}
                    {ACTION_LABELS[item.action] || item.action}
                    {' '}
                    {RESOURCE_LABELS[item.resource_type] || item.resource_type}
                  </span>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {relativeTime(item.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">暂无操作记录</p>
          )}
        </div>
      </div>
    </div>
  )
}
