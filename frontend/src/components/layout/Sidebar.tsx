import { useState } from 'react'
import { Link, useLocation } from '@tanstack/react-router'
import { useAppStore } from '@/stores/appStore'
import { usePermission } from '@/hooks/usePermission'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  FileText,
  BookOpen,
  Users2,
  BarChart3,
  CalendarClock,
  Wallet,
  Building2,
  Settings,
  Sparkles,
  ChevronLeft,
  Search,
  MessageSquare,
} from 'lucide-react'

interface MenuItem {
  label: string
  to: string
  icon: React.ReactNode
  permission?: string
  children?: MenuItem[]
}

const menuItems: MenuItem[] = [
  { label: '仪表盘', to: '/dashboard', icon: <LayoutDashboard size={20} /> },
  {
    label: '凭证管理',
    to: '/vouchers',
    icon: <FileText size={20} />,
    children: [
      { label: '凭证列表', to: '/vouchers', icon: <span /> },
      { label: '录入凭证', to: '/vouchers/new', icon: <span /> },
      { label: '凭证模板', to: '/vouchers/templates', icon: <span /> },
    ],
  },
  {
    label: '账表查询',
    to: '/ledgers',
    icon: <BookOpen size={20} />,
    children: [
      { label: '科目余额表', to: '/ledgers/trial-balance', icon: <span /> },
      { label: '总账', to: '/ledgers/general', icon: <span /> },
      { label: '三栏明细账', to: '/ledgers/detail', icon: <span /> },
      { label: '多栏明细账', to: '/ledgers/multi-column', icon: <span /> },
      { label: '序时账', to: '/ledgers/journal', icon: <span /> },
      { label: '数量金额账', to: '/ledgers/quantity', icon: <span /> },
    ],
  },
  { label: '辅助核算', to: '/auxiliary', icon: <Users2 size={20} /> },
  {
    label: '财务报表',
    to: '/reports',
    icon: <BarChart3 size={20} />,
    children: [
      { label: '资产负债表', to: '/reports/balance-sheet', icon: <span /> },
      { label: '利润表', to: '/reports/income', icon: <span /> },
      { label: '现金流量表', to: '/reports/cash-flow', icon: <span /> },
    ],
  },
  {
    label: '期末处理',
    to: '/period',
    icon: <CalendarClock size={20} />,
    children: [
      { label: '期初余额', to: '/period/opening-balances', icon: <span /> },
      { label: '期末结转', to: '/period/carry-forward', icon: <span /> },
      { label: '期末结账', to: '/period/close', icon: <span /> },
    ],
  },
  {
    label: '出纳管理',
    to: '/cashier',
    icon: <Wallet size={20} />,
    children: [
      { label: '现金日记账', to: '/cashier/cash', icon: <span /> },
      { label: '银行日记账', to: '/cashier/bank', icon: <span /> },
      { label: '银行对账', to: '/cashier/reconcile', icon: <span /> },
    ],
  },
  {
    label: '固定资产',
    to: '/assets',
    icon: <Building2 size={20} />,
    children: [
      { label: '资产卡片', to: '/assets/list', icon: <span /> },
      { label: '资产报表', to: '/assets/reports', icon: <span /> },
    ],
  },
  { label: 'AI 工作台', to: '/ai', icon: <Sparkles size={20} /> },
  {
    label: '系统管理',
    to: '/admin',
    icon: <Settings size={20} />,
    permission: 'admin:users',
    children: [
      { label: '用户管理', to: '/admin/users', icon: <span /> },
      { label: '角色管理', to: '/admin/roles', icon: <span /> },
      { label: '科目管理', to: '/admin/accounts', icon: <span /> },
      { label: '会计期间', to: '/admin/periods', icon: <span /> },
      { label: '系统参数', to: '/admin/params', icon: <span /> },
      { label: '审计日志', to: '/admin/audit-logs', icon: <span /> },
      { label: '数据备份', to: '/admin/backup', icon: <span /> },
    ],
  },
]

export function Sidebar() {
  const { sidebarOpen, toggleSidebar } = useAppStore()
  const { isAdmin } = usePermission()
  const location = useLocation()
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(['凭证管理', '账表查询', '财务报表', '期末处理', '出纳管理', '固定资产', '系统管理']))

  const toggleGroup = (label: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      return next
    })
  }

  const isActive = (to: string) => location.pathname.startsWith(to)

  const filterMenu = (items: MenuItem[]): MenuItem[] => {
    if (!searchTerm) return items
    return items.filter(
      (item) =>
        item.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.children?.some((c) => c.label.toLowerCase().includes(searchTerm.toLowerCase())),
    )
  }

  const renderMenuItem = (item: MenuItem, depth = 0) => {
    // Check permission
    if (item.permission === 'admin:users' && !isAdmin) return null

    if (item.children && item.children.length > 0) {
      const isExpanded = expandedGroups.has(item.label) || !!searchTerm
      const hasActiveChild = item.children.some((c) => isActive(c.to))
      const filteredChildren = searchTerm
        ? item.children.filter((c) => c.label.toLowerCase().includes(searchTerm.toLowerCase()))
        : item.children

      return (
        <div key={item.label}>
          <button
            onClick={() => toggleGroup(item.label)}
            className={cn(
              'flex w-full items-center gap-3 px-4 py-2 text-sm rounded-lg transition-colors',
              hasActiveChild
                ? 'text-accent bg-blue-50 border-l-2 border-accent'
                : 'text-foreground hover:bg-gray-100',
              !sidebarOpen && 'justify-center px-2',
            )}
            style={{ paddingLeft: sidebarOpen ? `${16 + depth * 12}px` : undefined }}
          >
            <span className="flex-shrink-0">{item.icon}</span>
            {sidebarOpen && (
              <>
                <span className="flex-1 text-left truncate">{item.label}</span>
                <span className="text-xs text-muted-foreground">
                  {isExpanded ? '▼' : '▶'}
                </span>
              </>
            )}
          </button>
          {sidebarOpen && isExpanded && filteredChildren.length > 0 && (
            <div className="ml-4">
              {filteredChildren.map((child) => renderMenuItem(child, depth + 1))}
            </div>
          )}
        </div>
      )
    }

    return (
      <Link
        key={item.to}
        to={item.to}
        className={cn(
          'flex items-center gap-3 px-4 py-2 text-sm rounded-lg transition-colors',
          isActive(item.to)
            ? 'text-accent bg-blue-50 border-l-2 border-accent font-medium'
            : 'text-foreground hover:bg-gray-100',
          !sidebarOpen && 'justify-center px-2',
        )}
      >
        <span className="flex-shrink-0">{item.icon}</span>
        {sidebarOpen && <span className="truncate">{item.label}</span>}
      </Link>
    )
  }

  const filteredItems = filterMenu(menuItems)

  return (
    <aside
      className={cn(
        'flex flex-col border-r bg-white transition-all duration-200',
        sidebarOpen ? 'w-60' : 'w-16',
      )}
    >
      {/* Search */}
      {sidebarOpen && (
        <div className="p-3">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-muted-foreground" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="搜索菜单..."
              className="w-full rounded-md border py-1.5 pl-8 pr-2 text-xs focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
        </div>
      )}

      {/* Menu items */}
      <nav className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
        {filteredItems.map((item) => renderMenuItem(item))}
      </nav>

      {/* Bottom: AI entry + collapse */}
      <div className="border-t p-2 space-y-1">
        <Link
          to="/ai"
          className={cn(
            'flex items-center gap-3 px-4 py-2 text-sm rounded-lg transition-colors',
            isActive('/ai') ? 'text-accent bg-blue-50' : 'text-foreground hover:bg-purple-50',
            !sidebarOpen && 'justify-center px-2',
          )}
        >
          <MessageSquare size={20} className="text-purple-500" />
          {sidebarOpen && <span>AI 助手</span>}
        </Link>
        <button
          onClick={toggleSidebar}
          className={cn(
            'flex w-full items-center gap-3 px-4 py-2 text-sm rounded-lg text-muted-foreground hover:bg-gray-100 transition-colors',
            !sidebarOpen && 'justify-center px-2',
          )}
        >
          <ChevronLeft
            size={20}
            className={cn('transition-transform', !sidebarOpen && 'rotate-180')}
          />
          {sidebarOpen && <span>收起菜单</span>}
        </button>
      </div>
    </aside>
  )
}
