import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { DataTable, type ColumnDef } from '@/components/DataTable/DataTable'
import { DataTablePagination } from '@/components/DataTable/DataTablePagination'
import { Search, X, ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

interface AuditLogItem {
  id: number
  user_id: string | null
  username: string | null
  action: string
  resource_type: string
  resource_id: string | null
  old_values: Record<string, unknown> | null
  new_values: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
  _type?: 'log' | 'diff'
  _parentId?: number
}

interface AuditLogResponse {
  items: AuditLogItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

const ACTION_LABELS: Record<string, string> = {
  INSERT: '创建',
  UPDATE: '更新',
  DELETE: '删除',
  'voucher:post': '记账',
  'voucher:audit': '审核',
  'period:close': '结账',
  'period:reopen': '反结账',
}

const RESOURCE_LABELS: Record<string, string> = {
  voucher: '凭证',
  account: '科目',
  period: '期间',
  user: '用户',
  role: '角色',
}

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function JSONDiff({ oldValues, newValues }: { oldValues: Record<string, unknown> | null; newValues: Record<string, unknown> | null }) {
  const oldEntries = oldValues ? Object.entries(oldValues).filter(([, v]) => v !== null) : []
  const newEntries = newValues ? Object.entries(newValues).filter(([, v]) => v !== null) : []
  const allKeys = [...new Set([...oldEntries.map(([k]) => k), ...newEntries.map(([k]) => k)])]

  if (allKeys.length === 0) return <span className="text-xs text-muted-foreground">无变更数据</span>

  return (
    <div className="text-xs font-mono">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b text-muted-foreground">
            <th className="text-left py-1 pr-4">字段</th>
            <th className="text-left py-1 pr-4 text-red-600">旧值</th>
            <th className="text-left py-1 text-green-600">新值</th>
          </tr>
        </thead>
        <tbody>
          {allKeys.map((key) => {
            const oldVal = oldValues?.[key]
            const newVal = newValues?.[key]
            const changed = JSON.stringify(oldVal) !== JSON.stringify(newVal)
            return (
              <tr key={key} className={cn('border-b border-gray-100', changed && 'bg-yellow-50/50')}>
                <td className="py-1 pr-4 text-muted-foreground">{key}</td>
                <td className={cn('py-1 pr-4', changed && 'text-red-600')}>
                  {oldVal !== undefined ? JSON.stringify(oldVal) : '-'}
                </td>
                <td className={cn('py-1', changed && 'text-green-600 font-medium')}>
                  {newVal !== undefined ? JSON.stringify(newVal) : '-'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function AuditLogViewer() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [userId, setUserId] = useState('')
  const [action, setAction] = useState('')
  const [resourceType, setResourceType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', page, pageSize, userId, action, resourceType, dateFrom, dateTo],
    queryFn: async () => {
      const params: Record<string, string | number> = { page, page_size: pageSize }
      if (userId) params.user_id = userId
      if (action) params.action = action
      if (resourceType) params.resource_type = resourceType
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      const { data } = await api.get<AuditLogResponse>('/admin/audit-logs', { params })
      return data
    },
  })

  // Interleave diff rows for expanded items
  const displayItems = useMemo(() => {
    if (!data) return []
    const result: AuditLogItem[] = []
    for (const item of data.items) {
      result.push({ ...item, _type: 'log' })
      if (expandedRows.has(item.id) && (item.old_values || item.new_values)) {
        result.push({ ...item, _type: 'diff', _parentId: item.id, id: -(item.id) })
      }
    }
    return result
  }, [data, expandedRows])

  function toggleRow(id: number) {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function clearFilters() {
    setUserId('')
    setAction('')
    setResourceType('')
    setDateFrom('')
    setDateTo('')
    setPage(1)
  }

  const hasFilters = userId || action || resourceType || dateFrom || dateTo

  const columns: ColumnDef<AuditLogItem>[] = [
    {
      key: 'created_at',
      header: '时间',
      cell: (item) => {
        if (item._type === 'diff') return null
        return <span className="text-sm">{formatDateTime(item.created_at)}</span>
      },
    },
    {
      key: 'username',
      header: '用户',
      cell: (item) => {
        if (item._type === 'diff') return null
        return <span className="text-sm">{item.username || item.user_id?.slice(0, 8) || '系统'}</span>
      },
    },
    {
      key: 'action',
      header: '操作',
      cell: (item) => {
        if (item._type === 'diff') return null
        const label = ACTION_LABELS[item.action] || item.action
        let color = 'bg-gray-100 text-gray-700'
        if (item.action === 'DELETE' || item.action === 'voucher:post') color = 'bg-orange-100 text-orange-700'
        else if (item.action === 'INSERT' || item.action === 'voucher:audit') color = 'bg-green-100 text-green-700'
        else if (item.action === 'UPDATE') color = 'bg-blue-100 text-blue-700'
        return <span className={cn('inline-block rounded px-2 py-0.5 text-xs font-medium', color)}>{label}</span>
      },
    },
    {
      key: 'resource_type',
      header: '资源类型',
      cell: (item) => {
        if (item._type === 'diff') return null
        return <span className="text-sm">{RESOURCE_LABELS[item.resource_type] || item.resource_type}</span>
      },
    },
    {
      key: 'resource_id',
      header: '资源ID',
      cell: (item) => {
        if (item._type === 'diff') return null
        return (
          <span className="text-xs font-mono text-muted-foreground">
            {item.resource_id?.slice(0, 8) || '-'}
          </span>
        )
      },
    },
    {
      key: 'ip_address',
      header: 'IP',
      cell: (item) => {
        if (item._type === 'diff') return null
        return <span className="text-sm">{item.ip_address || '-'}</span>
      },
    },
    {
      key: 'expand',
      header: '变更',
      cell: (item) => {
        if (item._type === 'diff') return null
        const hasDiff = item.old_values || item.new_values
        if (!hasDiff) return <span className="text-xs text-muted-foreground">-</span>
        const isExpanded = expandedRows.has(item.id)
        return (
          <button
            onClick={(e) => { e.stopPropagation(); toggleRow(item.id) }}
            className="flex items-center gap-1 text-xs text-accent hover:underline"
          >
            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            {isExpanded ? '收起' : '查看'}
          </button>
        )
      },
    },
    {
      key: 'diff_detail',
      header: '',
      className: 'p-0',
      headerClassName: 'p-0',
      cell: (item) => {
        if (item._type !== 'diff') return null
        return (
          <div className="px-4 py-3 bg-gray-50/50">
            <JSONDiff oldValues={item.old_values} newValues={item.new_values} />
          </div>
        )
      },
    },
  ]

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-1">审计日志</h2>
      <p className="text-sm text-muted-foreground mb-6">记录系统中所有数据变更操作，支持按用户、操作类型、资源类型和时间筛选</p>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div>
          <label className="block text-xs font-medium mb-1 text-muted-foreground">用户ID</label>
          <input
            type="text"
            value={userId}
            onChange={(e) => { setUserId(e.target.value); setPage(1) }}
            placeholder="UUID 前缀"
            className="w-36 rounded-md border px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        <div>
          <label className="block text-xs font-medium mb-1 text-muted-foreground">操作类型</label>
          <select
            value={action}
            onChange={(e) => { setAction(e.target.value); setPage(1) }}
            className="rounded-md border px-2.5 py-1.5 text-xs bg-background focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="">全部</option>
            {Object.entries(ACTION_LABELS).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium mb-1 text-muted-foreground">资源类型</label>
          <select
            value={resourceType}
            onChange={(e) => { setResourceType(e.target.value); setPage(1) }}
            className="rounded-md border px-2.5 py-1.5 text-xs bg-background focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="">全部</option>
            {Object.entries(RESOURCE_LABELS).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium mb-1 text-muted-foreground">开始日期</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1) }}
            className="rounded-md border px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        <div>
          <label className="block text-xs font-medium mb-1 text-muted-foreground">结束日期</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1) }}
            className="rounded-md border px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-gray-50"
          >
            <X size={14} />
            清除筛选
          </button>
        )}
        <span className="text-xs text-muted-foreground ml-auto">
          {data ? `共 ${data.total} 条记录` : ''}
        </span>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={displayItems}
        total={displayItems.length}
        page={page}
        pageSize={pageSize}
        onPaginationChange={(p, ps) => { setPage(p); setPageSize(ps) }}
        isLoading={isLoading}
        getId={(item) => {
          if (item._type === 'diff') return `diff-${item._parentId}`
          return String(item.id)
        }}
        footer={
          <DataTablePagination
            currentPage={page}
            totalPages={data?.pages || 1}
            totalItems={data?.total || 0}
            pageSize={pageSize}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        }
      />
    </div>
  )
}
