import { useRef, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { DataTable, type ColumnDef } from '@/components/DataTable/DataTable'
import { DataTablePagination } from '@/components/DataTable/DataTablePagination'
import { StatusBadge } from '@/components/StatusBadge'
import { Upload, X, FileText, Trash2 } from 'lucide-react'
import {
  useOriginalDocuments,
  useUploadDocument,
  useDeleteDocument,
  DOC_STATUS_MAP,
  DOC_TYPE_LABELS,
  type OriginalDocument,
} from '@/features/documents/useOriginalDocuments'

function formatDate(iso: string) {
  return iso.slice(0, 10)
}

function formatAmount(val?: string | null): string {
  if (!val) return '-'
  const n = parseFloat(val)
  if (!Number.isFinite(n) || n === 0) return '-'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${bytes} B`
}

function UploadDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [documentType, setDocumentType] = useState('other')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const uploadMutation = useUploadDocument()

  if (!open) return null

  function handleUpload() {
    if (!file) {
      setError('请选择文件')
      return
    }
    setError('')
    uploadMutation.mutate(
      { file, documentType },
      {
        onSuccess: () => {
          setFile(null)
          onClose()
        },
        onError: (err: unknown) => {
          const msg =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
            '上传失败，请重试'
          setError(msg)
        },
      },
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 className="text-lg font-semibold mb-4">上传原始凭证</h3>

        {error && (
          <div className="mb-3 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-600">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">票据类型</label>
            <select
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-accent"
            >
              {Object.entries(DOC_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">
              文件（图片 / PDF / Excel / CSV）
            </label>
            <input
              ref={inputRef}
              type="file"
              accept=".jpg,.jpeg,.png,.gif,.webp,.bmp,.pdf,.xlsx,.xls,.csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full rounded-md border px-3 py-2 text-sm file:mr-3 file:rounded file:border-0 file:bg-accent/10 file:px-2 file:py-1 file:text-xs file:text-accent"
            />
            {file && (
              <p className="mt-1 text-xs text-muted-foreground">
                {file.name}（{formatSize(file.size)}）
              </p>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-md border hover:bg-gray-50 transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleUpload}
            disabled={uploadMutation.isPending || !file}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent/90 disabled:opacity-50 transition-colors"
          >
            <Upload size={14} />
            {uploadMutation.isPending ? '上传中...' : '上传'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function DocumentList() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [showUpload, setShowUpload] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const { data, isLoading } = useOriginalDocuments({
    page,
    page_size: pageSize,
    keyword: keyword || undefined,
    status: statusFilter || undefined,
    document_type: typeFilter || undefined,
  })
  const deleteMutation = useDeleteDocument()

  const hasFilters = keyword || statusFilter || typeFilter

  function clearFilters() {
    setKeyword('')
    setStatusFilter('')
    setTypeFilter('')
    setPage(1)
  }

  function handleDelete(doc: OriginalDocument, e: React.MouseEvent) {
    e.stopPropagation()
    if (!window.confirm(`确定删除「${doc.file_name}」？此操作不可恢复。`)) return
    setDeleteError('')
    deleteMutation.mutate(doc.id, {
      onError: (err: unknown) => {
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          '删除失败'
        setDeleteError(msg)
      },
    })
  }

  const columns: ColumnDef<OriginalDocument>[] = [
    {
      key: 'file_name',
      header: '文件名',
      width: '26%',
      cell: (item) => (
        <span className="flex items-center gap-1.5 truncate text-sm">
          <FileText size={14} className="shrink-0 text-muted-foreground" />
          <Link
            to="/original-documents/$documentId"
            params={{ documentId: item.id }}
            className="truncate text-accent hover:underline"
          >
            {item.file_name}
          </Link>
        </span>
      ),
    },
    {
      key: 'document_type',
      header: '类型',
      width: '90px',
      cell: (item) => (
        <span className="text-sm">{DOC_TYPE_LABELS[item.document_type] || item.document_type}</span>
      ),
    },
    {
      key: 'status',
      header: '状态',
      width: '110px',
      cell: (item) => {
        const cfg = DOC_STATUS_MAP[item.status] || { label: item.status, colorKey: 'draft' }
        return <StatusBadge status={cfg.colorKey} label={cfg.label} />
      },
    },
    {
      key: 'total_amount',
      header: '金额',
      width: '120px',
      className: 'text-right',
      cell: (item) => (
        <span className="text-sm font-mono">{formatAmount(item.total_amount || item.amount)}</span>
      ),
    },
    {
      key: 'counterparty_name',
      header: '对方单位',
      width: '16%',
      cell: (item) => (
        <span className="block truncate text-sm text-muted-foreground">
          {item.counterparty_name || '-'}
        </span>
      ),
    },
    {
      key: 'voucher_no',
      header: '记账凭证',
      width: '150px',
      cell: (item) =>
        item.voucher_id ? (
          <Link
            to="/vouchers/$voucherId"
            params={{ voucherId: item.voucher_id }}
            onClick={(e) => e.stopPropagation()}
            className="font-mono text-sm text-accent hover:underline"
          >
            {item.voucher_no}
          </Link>
        ) : (
          <span className="text-sm text-muted-foreground">-</span>
        ),
    },
    {
      key: 'created_at',
      header: '上传时间',
      width: '110px',
      cell: (item) => <span className="text-sm">{formatDate(item.created_at)}</span>,
    },
    {
      key: 'actions',
      header: '',
      width: '48px',
      cell: (item) =>
        !item.voucher_id ? (
          <button
            onClick={(e) => handleDelete(item, e)}
            className="p-1 rounded hover:bg-red-100 text-muted-foreground hover:text-red-600"
            title="删除"
          >
            <Trash2 size={14} />
          </button>
        ) : null,
    },
  ]

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">原始凭证</h2>
          <p className="text-sm text-muted-foreground mt-1">
            上传票据附件，识别校对后生成记账凭证
          </p>
        </div>
        <button
          onClick={() => setShowUpload(true)}
          className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm text-white font-medium hover:bg-accent/90"
        >
          <Upload size={16} />
          上传票据
        </button>
      </div>

      {deleteError && (
        <div className="mb-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
          {deleteError}
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
            placeholder="文件名/对方单位/发票号..."
            className="w-52 rounded-md border px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-accent"
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
            {Object.entries(DOC_STATUS_MAP).map(([value, cfg]) => (
              <option key={value} value={value}>{cfg.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium mb-1 text-muted-foreground">票据类型</label>
          <select
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1) }}
            className="rounded-md border px-2.5 py-1.5 text-xs bg-background focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="">全部</option>
            {Object.entries(DOC_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
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
        getId={(row) => row.id}
        onRowClick={(row) => {
          navigate({ to: '/original-documents/$documentId', params: { documentId: row.id } })
        }}
        emptyMessage="暂无原始凭证，点击右上角上传票据"
        footer={
          <DataTablePagination
            page={page}
            total={data?.total || 0}
            pageSize={pageSize}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        }
      />

      <UploadDialog open={showUpload} onClose={() => setShowUpload(false)} />
    </div>
  )
}
