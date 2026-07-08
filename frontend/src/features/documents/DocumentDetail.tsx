import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { StatusBadge } from '@/components/StatusBadge'
import { Skeleton } from '@/components/Skeleton'
import {
  ArrowLeft,
  Download,
  FileText,
  Link2,
  Plus,
  ScanLine,
  Save,
  Trash2,
  AlertTriangle,
} from 'lucide-react'
import {
  useOriginalDocument,
  useRecognizeDocument,
  useUpdateDocument,
  useCreateVoucherDraft,
  useLinkVoucher,
  useDeleteDocument,
  documentFileUrl,
  DOC_STATUS_MAP,
  DOC_TYPE_LABELS,
  type OriginalDocument,
  type SuggestedEntry,
} from '@/features/documents/useOriginalDocuments'

function extractError(err: unknown, fallback: string): string {
  return (
    (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback
  )
}

// ── File preview (JWT-authenticated blob fetch) ──────

function FilePreview({ doc }: { doc: OriginalDocument }) {
  const [objectUrl, setObjectUrl] = useState('')
  const [failed, setFailed] = useState(false)

  const previewable =
    doc.content_type.startsWith('image/') || doc.content_type === 'application/pdf'

  useEffect(() => {
    if (!previewable) return
    let url = ''
    api
      .get(documentFileUrl(doc.id), { responseType: 'blob' })
      .then(({ data }) => {
        url = URL.createObjectURL(data)
        setObjectUrl(url)
      })
      .catch(() => setFailed(true))
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [doc.id, doc.content_type, previewable])

  async function handleDownload() {
    try {
      const { data } = await api.get(documentFileUrl(doc.id), {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(data)
      const a = document.createElement('a')
      a.href = url
      a.download = doc.file_name
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setFailed(true)
    }
  }

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      <div className="flex items-center justify-between border-b px-4 py-2.5">
        <span className="flex items-center gap-1.5 text-sm font-medium truncate">
          <FileText size={14} className="shrink-0 text-muted-foreground" />
          {doc.file_name}
        </span>
        <button
          onClick={handleDownload}
          className="flex items-center gap-1 text-xs text-accent hover:underline shrink-0"
        >
          <Download size={13} />
          下载
        </button>
      </div>
      <div className="bg-gray-50 min-h-[320px] max-h-[70vh] flex items-center justify-center overflow-auto">
        {failed ? (
          <p className="text-sm text-muted-foreground p-8">文件加载失败</p>
        ) : !previewable ? (
          <div className="text-center p-8 text-sm text-muted-foreground">
            <FileText size={40} className="mx-auto mb-2 opacity-40" />
            <p>{doc.content_type}</p>
            <p className="mt-1">该文件类型不支持预览，请下载查看</p>
          </div>
        ) : !objectUrl ? (
          <p className="text-sm text-muted-foreground p-8">加载中...</p>
        ) : doc.content_type === 'application/pdf' ? (
          <iframe src={objectUrl} title={doc.file_name} className="w-full h-[70vh]" />
        ) : (
          <img src={objectUrl} alt={doc.file_name} className="max-w-full max-h-[70vh]" />
        )}
      </div>
    </div>
  )
}

// ── Link-existing-voucher dialog ─────────────────────

interface VoucherOption {
  id: string
  voucher_no: string
  date: string
  status: string
}

function LinkVoucherDialog({
  open,
  documentId,
  onClose,
}: {
  open: boolean
  documentId: string
  onClose: () => void
}) {
  const [keyword, setKeyword] = useState('')
  const [error, setError] = useState('')
  const linkMutation = useLinkVoucher()

  const { data } = useQuery({
    queryKey: ['voucher-search', keyword],
    queryFn: async () => {
      const { data } = await api.get<{ items: VoucherOption[] }>('/vouchers', {
        params: { page_size: 10, keyword: keyword || undefined },
      })
      return data.items
    },
    enabled: open,
  })

  if (!open) return null

  function handleLink(voucherId: string) {
    setError('')
    linkMutation.mutate(
      { id: documentId, voucherId },
      {
        onSuccess: onClose,
        onError: (err) => setError(extractError(err, '关联失败')),
      },
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 p-6">
        <h3 className="text-lg font-semibold mb-3">关联已有凭证</h3>
        {error && (
          <div className="mb-3 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-600">
            {error}
          </div>
        )}
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="按凭证号搜索..."
          className="w-full rounded-md border px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-accent"
        />
        <div className="max-h-64 overflow-auto border rounded-md divide-y">
          {(data || []).map((v) => (
            <button
              key={v.id}
              onClick={() => handleLink(v.id)}
              disabled={linkMutation.isPending}
              className="w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-accent/5 disabled:opacity-50"
            >
              <span className="font-mono">{v.voucher_no}</span>
              <span className="text-xs text-muted-foreground">{v.date.slice(0, 10)}</span>
            </button>
          ))}
          {data && data.length === 0 && (
            <p className="px-3 py-4 text-sm text-muted-foreground text-center">无匹配凭证</p>
          )}
        </div>
        <div className="flex justify-end mt-4">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-md border hover:bg-gray-50"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ────────────────────────────────────────

export default function DocumentDetail() {
  const { documentId } = useParams({ from: '/authenticated/original-documents/$documentId' })
  const navigate = useNavigate()
  const { data: doc, isLoading } = useOriginalDocument(documentId)

  const recognizeMutation = useRecognizeDocument()
  const updateMutation = useUpdateDocument()
  const draftMutation = useCreateVoucherDraft()
  const deleteMutation = useDeleteDocument()

  const [form, setForm] = useState({
    document_type: 'other',
    issue_date: '',
    total_amount: '',
    tax_amount: '',
    counterparty_name: '',
    invoice_no: '',
    summary: '',
  })
  const [entries, setEntries] = useState<SuggestedEntry[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [showLink, setShowLink] = useState(false)

  // Sync server state → local form whenever the document (re)loads
  useEffect(() => {
    if (!doc) return
    setForm({
      document_type: doc.document_type,
      issue_date: doc.issue_date || '',
      total_amount: doc.total_amount || '',
      tax_amount: doc.tax_amount || '',
      counterparty_name: doc.counterparty_name || '',
      invoice_no: doc.invoice_no || '',
      summary: doc.summary || '',
    })
    setEntries(doc.recognized_fields?.suggested_entries || [])
  }, [doc])

  if (isLoading) {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <Skeleton variant="text" className="h-8 w-48 mb-6" />
        <Skeleton variant="card" />
      </div>
    )
  }

  if (!doc) {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <button
          onClick={() => navigate({ to: '/original-documents' })}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft size={16} />
          返回原始凭证列表
        </button>
        <div className="rounded-lg border bg-card p-12 text-center">
          <p className="text-lg text-red-600 font-medium">原始凭证未找到</p>
        </div>
      </div>
    )
  }

  const statusCfg = DOC_STATUS_MAP[doc.status] || { label: doc.status, colorKey: 'draft' }
  const locked = doc.status === 'voucher_created' || doc.status === 'archived'
  const warnings = doc.recognized_fields?.warnings || []

  function updateEntry(idx: number, field: keyof SuggestedEntry, value: string) {
    setEntries((prev) => prev.map((e, i) => (i === idx ? { ...e, [field]: value } : e)))
  }

  function handleRecognize() {
    setError('')
    setMessage('')
    recognizeMutation.mutate(documentId, {
      onSuccess: () => setMessage('识别完成，请核对识别字段'),
      onError: (err) => setError(extractError(err, '识别失败')),
    })
  }

  function handleSave() {
    setError('')
    setMessage('')
    updateMutation.mutate(
      {
        id: documentId,
        body: {
          document_type: form.document_type,
          issue_date: form.issue_date || null,
          total_amount: form.total_amount || null,
          tax_amount: form.tax_amount || null,
          counterparty_name: form.counterparty_name || null,
          invoice_no: form.invoice_no || null,
          summary: form.summary || null,
          recognized_fields: {
            ...(doc?.recognized_fields || {}),
            suggested_entries: entries,
          },
        },
      },
      {
        onSuccess: () => setMessage('校对已保存'),
        onError: (err) => setError(extractError(err, '保存失败')),
      },
    )
  }

  function handleCreateDraft() {
    setError('')
    setMessage('')
    draftMutation.mutate(documentId, {
      onSuccess: (data) => {
        navigate({ to: '/vouchers/$voucherId', params: { voucherId: data.voucher_id } })
      },
      onError: (err) => setError(extractError(err, '生成凭证草稿失败')),
    })
  }

  function handleDelete() {
    if (!doc || !window.confirm(`确定删除「${doc.file_name}」？此操作不可恢复。`)) return
    deleteMutation.mutate(documentId, {
      onSuccess: () => navigate({ to: '/original-documents' }),
      onError: (err) => setError(extractError(err, '删除失败')),
    })
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <button
        onClick={() => navigate({ to: '/original-documents' })}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-3"
      >
        <ArrowLeft size={16} />
        返回原始凭证列表
      </button>

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <h2 className="text-2xl font-bold truncate">{doc.file_name}</h2>
          <StatusBadge status={statusCfg.colorKey} label={statusCfg.label} />
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {!locked && (
            <button
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              className="flex items-center gap-1.5 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
            >
              <Trash2 size={14} />
              删除
            </button>
          )}
        </div>
      </div>

      {message && (
        <div className="mb-4 rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">
          {message}
        </div>
      )}
      {error && (
        <div className="mb-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Linked voucher banner */}
      {doc.voucher_id && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          <Link2 size={15} />
          已生成记账凭证
          <Link
            to="/vouchers/$voucherId"
            params={{ voucherId: doc.voucher_id }}
            className="font-mono font-medium text-accent hover:underline"
          >
            {doc.voucher_no}
          </Link>
        </div>
      )}

      {/* Recognition warnings */}
      {warnings.length > 0 && !locked && (
        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span className="flex items-center gap-1.5 font-medium mb-1">
            <AlertTriangle size={14} />
            识别提示
          </span>
          <ul className="list-disc list-inside space-y-0.5">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: file preview */}
        <FilePreview doc={doc} />

        {/* Right: recognized fields + suggested entries */}
        <div className="space-y-4">
          <div className="rounded-lg border bg-card">
            <div className="flex items-center justify-between border-b px-4 py-2.5">
              <span className="text-sm font-medium">识别字段</span>
              {doc.recognition_confidence && (
                <span className="text-xs text-muted-foreground">
                  置信度 {(parseFloat(doc.recognition_confidence) * 100).toFixed(0)}%
                </span>
              )}
            </div>
            <div className="p-4 grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">票据类型</label>
                <select
                  value={form.document_type}
                  onChange={(e) => setForm({ ...form, document_type: e.target.value })}
                  disabled={locked}
                  className="w-full rounded-md border px-2.5 py-1.5 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-accent disabled:bg-gray-50 disabled:text-muted-foreground"
                >
                  {Object.entries(DOC_TYPE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">票据日期</label>
                <input
                  type="date"
                  value={form.issue_date}
                  onChange={(e) => setForm({ ...form, issue_date: e.target.value })}
                  disabled={locked}
                  className="w-full rounded-md border px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-accent disabled:bg-gray-50 disabled:text-muted-foreground"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">价税合计</label>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.total_amount}
                  onChange={(e) => setForm({ ...form, total_amount: e.target.value })}
                  disabled={locked}
                  className="w-full rounded-md border px-2.5 py-1.5 text-sm text-right font-mono focus:outline-none focus:ring-1 focus:ring-accent disabled:bg-gray-50 disabled:text-muted-foreground"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">税额</label>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.tax_amount}
                  onChange={(e) => setForm({ ...form, tax_amount: e.target.value })}
                  disabled={locked}
                  className="w-full rounded-md border px-2.5 py-1.5 text-sm text-right font-mono focus:outline-none focus:ring-1 focus:ring-accent disabled:bg-gray-50 disabled:text-muted-foreground"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">对方单位</label>
                <input
                  type="text"
                  value={form.counterparty_name}
                  onChange={(e) => setForm({ ...form, counterparty_name: e.target.value })}
                  disabled={locked}
                  className="w-full rounded-md border px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-accent disabled:bg-gray-50 disabled:text-muted-foreground"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">发票号码</label>
                <input
                  type="text"
                  value={form.invoice_no}
                  onChange={(e) => setForm({ ...form, invoice_no: e.target.value })}
                  disabled={locked}
                  className="w-full rounded-md border px-2.5 py-1.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-accent disabled:bg-gray-50 disabled:text-muted-foreground"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-xs font-medium text-muted-foreground mb-1">摘要</label>
                <input
                  type="text"
                  value={form.summary}
                  onChange={(e) => setForm({ ...form, summary: e.target.value })}
                  disabled={locked}
                  className="w-full rounded-md border px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-accent disabled:bg-gray-50 disabled:text-muted-foreground"
                />
              </div>
            </div>
          </div>

          {/* Suggested entries */}
          <div className="rounded-lg border bg-card overflow-hidden">
            <div className="flex items-center justify-between border-b px-4 py-2.5">
              <span className="text-sm font-medium">建议分录</span>
              {!locked && (
                <button
                  onClick={() =>
                    setEntries((prev) => [
                      ...prev,
                      { account_code: '', summary: form.summary, debit_amount: '0', credit_amount: '0' },
                    ])
                  }
                  className="flex items-center gap-1 text-xs text-accent hover:underline"
                >
                  <Plus size={13} />
                  添加行
                </button>
              )}
            </div>
            {entries.length === 0 ? (
              <p className="px-4 py-6 text-sm text-muted-foreground text-center">
                暂无建议分录，点击「运行识别」自动生成
              </p>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground w-24">科目编码</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">摘要</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground w-28">借方</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground w-28">贷方</th>
                    {!locked && <th className="w-10" />}
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry, idx) => (
                    <tr key={idx} className="border-b last:border-b-0">
                      <td className="px-1.5 py-1">
                        <input
                          type="text"
                          value={entry.account_code}
                          onChange={(e) => updateEntry(idx, 'account_code', e.target.value)}
                          disabled={locked}
                          className="w-full rounded border px-2 py-1 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-accent disabled:bg-gray-50"
                        />
                      </td>
                      <td className="px-1.5 py-1">
                        <input
                          type="text"
                          value={entry.summary}
                          onChange={(e) => updateEntry(idx, 'summary', e.target.value)}
                          disabled={locked}
                          className="w-full rounded border px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-accent disabled:bg-gray-50"
                        />
                      </td>
                      <td className="px-1.5 py-1">
                        <input
                          type="number"
                          min={0}
                          step="0.01"
                          value={entry.debit_amount}
                          onChange={(e) => updateEntry(idx, 'debit_amount', e.target.value)}
                          disabled={locked}
                          className="w-full rounded border px-2 py-1 text-sm text-right font-mono focus:outline-none focus:ring-1 focus:ring-accent disabled:bg-gray-50"
                        />
                      </td>
                      <td className="px-1.5 py-1">
                        <input
                          type="number"
                          min={0}
                          step="0.01"
                          value={entry.credit_amount}
                          onChange={(e) => updateEntry(idx, 'credit_amount', e.target.value)}
                          disabled={locked}
                          className="w-full rounded border px-2 py-1 text-sm text-right font-mono focus:outline-none focus:ring-1 focus:ring-accent disabled:bg-gray-50"
                        />
                      </td>
                      {!locked && (
                        <td className="px-1.5 py-1 text-center">
                          <button
                            onClick={() => setEntries((prev) => prev.filter((_, i) => i !== idx))}
                            className="p-1 rounded hover:bg-red-100 text-muted-foreground hover:text-red-600"
                            title="删除行"
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Actions */}
          {!locked && (
            <div className="flex flex-wrap gap-2">
              <button
                onClick={handleRecognize}
                disabled={recognizeMutation.isPending}
                className="flex items-center gap-1.5 rounded-md border border-accent px-4 py-2 text-sm text-accent font-medium hover:bg-accent/5 disabled:opacity-50"
              >
                <ScanLine size={15} />
                {recognizeMutation.isPending ? '识别中...' : '运行识别'}
              </button>
              <button
                onClick={handleSave}
                disabled={updateMutation.isPending}
                className="flex items-center gap-1.5 rounded-md border px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
              >
                <Save size={15} />
                {updateMutation.isPending ? '保存中...' : '保存校对'}
              </button>
              <div className="flex gap-2 ml-auto">
                <button
                  onClick={() => setShowLink(true)}
                  className="flex items-center gap-1.5 rounded-md border px-4 py-2 text-sm font-medium hover:bg-gray-50"
                >
                  <Link2 size={15} />
                  关联已有凭证
                </button>
                <Link
                  to="/vouchers/new"
                  search={{ documentId }}
                  className="flex items-center gap-1.5 rounded-md border border-accent px-4 py-2 text-sm text-accent font-medium hover:bg-accent/5"
                >
                  <FileText size={15} />
                  手工编制凭证
                </Link>
                <button
                  onClick={handleCreateDraft}
                  disabled={draftMutation.isPending}
                  className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm text-white font-medium hover:bg-accent/90 disabled:opacity-50"
                >
                  <Plus size={15} />
                  {draftMutation.isPending ? '生成中...' : '生成凭证草稿'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <LinkVoucherDialog open={showLink} documentId={documentId} onClose={() => setShowLink(false)} />
    </div>
  )
}
