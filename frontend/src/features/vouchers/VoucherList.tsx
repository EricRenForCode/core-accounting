import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import api from '@/lib/api'
import { DataTable, type ColumnDef } from '@/components/DataTable/DataTable'
import { DataTablePagination } from '@/components/DataTable/DataTablePagination'
import { StatusBadge } from '@/components/StatusBadge'
import { Plus, Search, X, CheckCircle, BookOpen } from 'lucide-react'

interface VoucherItem {
  id: string
  voucher_no: string
  date: string
  period_id: string
  attachments: number
  status: string
  creator_id: string
  created_at: string
  entries: Array<{
    id: string
    summary: string
    debit_amount: string
    credit_amount: string
  }>
}

interface VoucherListResponse {
  items: VoucherItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

const STATUS_MAP: Record<string, { label: string; color: 'default' | 'success' | 'warning' | 'info' }> = {
  draft: { label: '草稿', color: 'default' },
  audited: { label: '已审核', color: 'info' },
  posted: { label: '已记账', color: 'success' },
  reversed: { label: '已冲销', color: 'warning' },
}

function formatDate(iso: string) {
  return iso.slice(0, 10)
}

function getFirstSummary(entries: VoucherItem['entries']): string {
  if (!entries || entries.length === 0) return '-'
  return entries[0].summary.length > 30
    ? entries[0].summary.slice(0, 30) + '...'
    : entries[0].summary
}

function getTotals(entries: VoucherItem['entries']): { debit: number; credit: number } {
  if (!entries) return { debit: 0, credit: 0 }
  return {
    debit: entries.reduce((s, e) => s + parseFloat(e.debit_amount || '0'), 0),
    credit: entries.reduce((s, e) => s + parseFloat(e.credit_amount || '0'), 0),
  }
}

export default function VoucherList() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sort, setSort] = useState('date')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [batchError, setBatchError] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['vouchers', page, pageSize, keyword, statusFilter, dateFrom, dateTo, sort, sortOrder],
    queryFn: async () => {
      const params: Record<string, string | number> = { page, page_size: pageSize, sort, order: sortOrder }
      if (keyword) params.keyword = keyword
      if (statusFilter) params.status = statusFilter
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      const { data } = await api.get<VoucherListResponse>('/vouchers', { params })
      return data
    },
  })

  function clearFilters() {
    setKeyword('')
    setStatusFilter('')
    setDateFrom('')
    setDateTo('')
    setPage(1)
  }

  // Batch approve mutation
  const batchApproveMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      const results = await Promise.allSettled(
        ids.map((id) => api.post(`/vouchers/${id}/audit`)),
      )
      const failed = results.filter((r) => r.status === 'rejected')
      if (failed.length > 0) throw new Error(`${failed.length} 个凭证审核失败`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vouchers'] })
      setSelectedIds([])
      setBatchError('')
    },
    onError: (err: unknown) => {
      const msg = (err as { message?: string })?.message || '批量审核失败'
      setBatchError(msg)
    },
  })

  // Batch post mutation
  const batchPostMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      const results = await Promise.allSettled(
        ids.map((id) => api.post(`/vouchers/${id}/post`)),
      )
      const failed = results.filter((r) => r.status === 'rejected')
      if (failed.length > 0) throw new Error(`${failed.length} 个凭证记账失败`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vouchers'] })
      setSelectedIds([])
      setBatchError('')
    },
    onError: (err: unknown) => {
      const msg = (err as { message?: string })?.message || '批量记账失败'
      setBatchError(msg)
    },
  })

  const hasFilters = keyword || statusFilter || dateFrom || dateTo
  const isBatchProcessing = batchApproveMutation.isPending || batchPostMutation.isPending

  const columns: ColumnDef<VoucherItem>[] = [
    {
      key: 'voucher_no',
      header: '凭证号',
      accessorKey: 'voucher_no',
      sortable: true,
      cell: (item) => (
        <Link
          to="/vouchers/$voucherId"
          params={{ voucherId: item.id }}
          className="font-mono text-sm text-accent hover:underline"
        >
          {item.voucher_no}
        </Link>
      ),
    },
    {
      key: 'date',
      header: '日期',
      sortable: true,
      cell: (item) => <span className="text-sm">{formatDate(item.date)}</span>,
    },
    {
      key: 'summary',
      header: '摘要',
      cell: (item) => (
        <span className="text-sm text-muted-foreground max-w-[300px] truncate block">
          {getFirstSummary(item.entries)}
        </span>
      ),
    },
    {
      key: 'debit',
      header: '借方合计',
      className: 'text-right',
      cell: (item) => {
        const { debit } = getTotals(item.entries)
        return (
          <span className="text-sm font-mono">
            {debit > 0 ? debit.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : ''}
          </span>
        )
      },
    },
    {
      key: 'credit',
      header: '贷方合计',
      className: 'text-right',
      cell: (item) => {
        const { credit } = getTotals(item.entries)
        return (
          <span className="text-sm font-mono">
            {credit > 0 ? credit.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : ''}
          </span>
        )
      },
    },
    {
      key: 'status',
      header: '状态',
      cell: (item) => {
        const cfg = STATUS_MAP[item.status] || { label: item.status, color: 'default' as const }
        return <StatusBadge status={item.status} label={cfg.label} />
      },
    },
    {
      key: 'attachments',
      header: '附件',
      cell: (item) => (
        <span className="text-sm text-muted-foreground">
          {item.attachments > 0 ? item.attachments : '-'}
        </span>
      ),
    },
  ]

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">凭证列表</h2>
          <p className="text-sm text-muted-foreground mt-1">管理和查询所有会计凭证</p>
        </div>
        <Link
          to="/vouchers/new"
          className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm text-white font-medium hover:bg-accent/90"
        >
          <Plus size={16} />
          录入凭证
        </Link>
      </div>

      {/* Batch Actions Bar */}
      {selectedIds.length > 0 && (
        <div className="flex items-center gap-3 mb-4 rounded-md border bg-accent/5 px-4 py-3">
          <span className="text-sm font-medium">
            已选择 <span className="text-accent">{selectedIds.length}</span> 条凭证
          </span>
          <div className="flex gap-2 ml-auto">
            <button
              onClick={() => {
                if (!window.confirm(`确定审核 ${selectedIds.length} 张凭证?`)) return
                batchApproveMutation.mutate(selectedIds)
              }}
              disabled={isBatchProcessing}
              className="flex items-center gap-1 rounded-md border border-green-300 bg-green-50 px-3 py-1.5 text-xs text-green-700 font-medium hover:bg-green-100 disabled:opacity-50"
            >
              <CheckCircle size={14} />
              批量审核
            </button>
            <button
              onClick={() => {
                if (!window.confirm(`确定记账 ${selectedIds.length} 张凭证? 记账后将不可修改。`)) return
                batchPostMutation.mutate(selectedIds)
              }}
              disabled={isBatchProcessing}
              className="flex items-center gap-1 rounded-md border border-blue-300 bg-blue-50 px-3 py-1.5 text-xs text-blue-700 font-medium hover:bg-blue-100 disabled:opacity-50"
            >
              <BookOpen size={14} />
              批量记账
            </button>
            <button
              onClick={() => setSelectedIds([])}
              className="rounded-md border px-3 py-1.5 text-xs text-muted-foreground hover:bg-gray-50"
            >
              取消选择
            </button>
          </div>
          {batchError && (
            <span className="text-xs text-red-600">{batchError}</span>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div>
          <label className="block text-xs font-medium mb-1 text-muted-foreground">关键词</label>
          <input
            type="text"
            value={keyword}
            onChange={(e) => { setKeyword(e.target.value); setPage(1) }}
            placeholder="凭证号/摘要..."
            className="w-44 rounded-md border px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        <div>
          <label className="block text-xs font-medium mb-1 text-muted-foreground">状态</label>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
            className="rounded-md border px-2.5 py-1.5 text-xs bg-background focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="">全部</option>
            <option value="draft">草稿</option>
            <option value="audited">已审核</option>
            <option value="posted">已记账</option>
            <option value="reversed">已冲销</option>
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
          {data ? `共 ${data.total} 条` : ''}
        </span>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={data?.items || []}
        total={data?.total || 0}
        page={page}
        pageSize={pageSize}
        onPaginationChange={(p, ps) => { setPage(p); setPageSize(ps) }}
        isLoading={isLoading}
        sort={sort}
        sortOrder={sortOrder}
        onSortChange={(s, o) => { setSort(s); setSortOrder(o) }}
        selectable
        selectedRows={selectedIds}
        onSelectionChange={setSelectedIds}
        getId={(row) => row.id}
        onRowClick={(row) => { navigate({ to: '/vouchers/$voucherId', params: { voucherId: row.id } }) }}
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
