import { useState } from 'react'
import { Link, useParams, useNavigate } from '@tanstack/react-router'
import { useVoucher, useAuditVoucher, useUnauditVoucher } from '@/features/vouchers/useVouchers'
import {
  useVoucherDocuments,
  DOC_STATUS_MAP,
  DOC_TYPE_LABELS,
} from '@/features/documents/useOriginalDocuments'
import { useUserStore } from '@/stores/userStore'
import { StatusBadge } from '@/components/StatusBadge'
import { BalanceBar } from '@/components/BalanceBar'
import { Skeleton } from '@/components/Skeleton'
import { ArrowLeft, CheckCircle, XCircle, Undo2, ChevronDown, ChevronRight, Paperclip, FileText } from 'lucide-react'
import type { VoucherEntry } from '@/features/vouchers/useVouchers'

const STATUS_MAP: Record<string, { label: string; color: 'default' | 'success' | 'warning' | 'info' }> = {
  draft: { label: '草稿', color: 'default' },
  audited: { label: '已审核', color: 'info' },
  posted: { label: '已记账', color: 'success' },
  reversed: { label: '已冲销', color: 'warning' },
}

function formatDate(iso: string): string {
  return iso.slice(0, 10)
}

function formatNumber(val: string | number): string {
  const n = typeof val === 'string' ? parseFloat(val) : val
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function EntryRow({ entry }: { entry: VoucherEntry }) {
  const [expanded, setExpanded] = useState(false)
  const hasAux = entry.auxiliaries && entry.auxiliaries.length > 0

  return (
    <>
      <tr className="border-b last:border-b-0 hover:bg-gray-50/50">
        <td className="px-3 py-2.5 text-center text-sm text-muted-foreground font-mono">
          {entry.row_number}
        </td>
        <td className="px-3 py-2.5 text-sm">
          <span className="font-mono text-xs text-muted-foreground mr-1.5">{entry.account_code}</span>
          <span>{entry.account_name}</span>
        </td>
        <td className="px-3 py-2.5 text-sm">{entry.summary}</td>
        <td className="px-3 py-2.5 text-right text-sm font-mono">
          {parseFloat(entry.debit_amount) > 0
            ? formatNumber(entry.debit_amount)
            : ''}
        </td>
        <td className="px-3 py-2.5 text-right text-sm font-mono">
          {parseFloat(entry.credit_amount) > 0
            ? formatNumber(entry.credit_amount)
            : ''}
        </td>
        <td className="px-3 py-2.5 text-center">
          {hasAux && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="inline-flex items-center gap-0.5 text-xs text-accent hover:underline"
            >
              {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              辅助核算
            </button>
          )}
        </td>
      </tr>
      {expanded && hasAux && (
        <tr key={`${entry.id}-aux`} className="bg-gray-50/50">
          <td colSpan={6} className="px-6 py-2">
            <div className="flex flex-wrap gap-3 text-xs">
              {entry.auxiliaries.map((aux) => (
                <span key={aux.id} className="inline-flex items-center gap-1 rounded border px-2 py-1 bg-white">
                  <span className="text-muted-foreground font-medium">{aux.aux_type}</span>
                  <span>{aux.aux_entity_name || aux.aux_entity_id}</span>
                </span>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function RejectDialog({
  open,
  onConfirm,
  onCancel,
}: {
  open: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const [reason, setReason] = useState('')

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onCancel} />
      <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 className="text-lg font-semibold text-foreground mb-2">驳回凭证</h3>
        <p className="text-sm text-muted-foreground mb-4">
          请输入驳回原因（此操作仅记录，不会调用后端接口）
        </p>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="请输入驳回原因..."
          className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent min-h-[100px] resize-y"
        />
        <div className="flex justify-end gap-3 mt-4">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium rounded-md border hover:bg-gray-50 transition-colors"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm font-medium rounded-md bg-red-600 hover:bg-red-600/90 text-white transition-colors"
          >
            确认驳回
          </button>
        </div>
      </div>
    </div>
  )
}

export default function VoucherDetail() {
  const { voucherId } = useParams({ from: '/authenticated/vouchers/$voucherId' })
  const navigate = useNavigate()
  const can = useUserStore((s) => s.can)

  const { data: voucher, isLoading, isError, error } = useVoucher(voucherId)
  const { data: linkedDocuments } = useVoucherDocuments(voucherId)
  const auditMutation = useAuditVoucher()
  const unauditMutation = useUnauditVoucher()

  const [showRejectDialog, setShowRejectDialog] = useState(false)
  const [rejectMessage, setRejectMessage] = useState('')

  // Loading state
  if (isLoading) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <Skeleton variant="text" className="h-8 w-48 mb-6" />
        <Skeleton variant="card" className="mb-4" />
        <Skeleton variant="table-row" count={5} />
      </div>
    )
  }

  // Error state
  if (isError || !voucher) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <button
          onClick={() => navigate({ to: '/vouchers' })}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft size={16} />
          返回凭证列表
        </button>
        <div className="rounded-lg border bg-card p-12 text-center">
          <p className="text-lg text-red-600 font-medium mb-2">凭证未找到</p>
          <p className="text-sm text-muted-foreground">
            {(error as { message?: string })?.message || '找不到该凭证，或无权访问'}
          </p>
        </div>
      </div>
    )
  }

  const statusCfg = STATUS_MAP[voucher.status] || { label: voucher.status, color: 'default' as const }
  const totalDebit = voucher.entries.reduce((s, e) => s + parseFloat(e.debit_amount || '0'), 0)
  const totalCredit = voucher.entries.reduce((s, e) => s + parseFloat(e.credit_amount || '0'), 0)
  const canAudit = can('voucher:audit')
  const canUnaudit = can('voucher:unaudit')

  function handleAudit() {
    auditMutation.mutate(voucherId)
  }

  function handleUnaudit() {
    unauditMutation.mutate(voucherId)
  }

  function handleRejectConfirm() {
    setShowRejectDialog(false)
    setRejectMessage('凭证已驳回')
    setTimeout(() => setRejectMessage(''), 3000)
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Toast-style rejection message */}
      {rejectMessage && (
        <div className="fixed top-4 right-4 z-50 rounded-md bg-red-600 text-white px-4 py-3 text-sm shadow-lg animate-in fade-in slide-in-from-top-2">
          {rejectMessage}
        </div>
      )}

      {/* Back nav + Header */}
      <button
        onClick={() => navigate({ to: '/vouchers' })}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-3"
      >
        <ArrowLeft size={16} />
        返回凭证列表
      </button>

      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-bold font-mono">{voucher.voucher_no}</h2>
          <StatusBadge status={voucher.status} label={statusCfg.label} />
        </div>
        <div className="flex items-center gap-2">
          {canAudit && voucher.status === 'draft' && auditMutation.isPending && (
            <span className="text-xs text-muted-foreground">审核中...</span>
          )}
          {canUnaudit && voucher.status === 'audited' && unauditMutation.isPending && (
            <span className="text-xs text-muted-foreground">反审核中...</span>
          )}
        </div>
      </div>

      {/* Metadata Card */}
      <div className="rounded-lg border bg-card mb-4">
        <div className="p-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-0.5">凭证日期</label>
            <span className="text-sm font-medium">{formatDate(voucher.date)}</span>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-0.5">附单据数</label>
            <span className="text-sm font-medium inline-flex items-center gap-1">
              <Paperclip size={14} />
              {voucher.attachments > 0 ? voucher.attachments : '无'}
            </span>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-0.5">制单人</label>
            <span className="text-sm font-medium">{voucher.creator_name}</span>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-0.5">审核人</label>
            <span className="text-sm font-medium">
              {voucher.auditor_id && voucher.auditor_name ? voucher.auditor_name : '—'}
            </span>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-0.5">来源</label>
            <span className="text-sm font-medium capitalize">{voucher.source || '—'}</span>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-0.5">记账时间</label>
            <span className="text-sm font-medium">
              {voucher.posted_at ? formatDate(voucher.posted_at) : '—'}
            </span>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-0.5">创建时间</label>
            <span className="text-sm text-muted-foreground">{formatDate(voucher.created_at)}</span>
          </div>
        </div>
      </div>

      {/* Entries Table */}
      <div className="rounded-lg border bg-card mb-4 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="w-10 px-3 py-2.5 text-center text-xs font-medium text-muted-foreground">#</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">科目</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">摘要</th>
                <th className="w-36 px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">借方金额</th>
                <th className="w-36 px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">贷方金额</th>
                <th className="w-24 px-3 py-2.5 text-center text-xs font-medium text-muted-foreground">辅助核算</th>
              </tr>
            </thead>
            <tbody>
              {voucher.entries.map((entry) => (
                <EntryRow key={entry.id} entry={entry} />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Balance Bar */}
      <div className="mb-4">
        <BalanceBar totalDebit={totalDebit} totalCredit={totalCredit} />
      </div>

      {/* Linked original documents (原始凭证) */}
      {linkedDocuments && linkedDocuments.items.length > 0 && (
        <div className="rounded-lg border bg-card mb-4 overflow-hidden">
          <div className="border-b px-4 py-2.5">
            <span className="text-sm font-medium inline-flex items-center gap-1.5">
              <Paperclip size={14} />
              关联原始凭证（{linkedDocuments.items.length}）
            </span>
          </div>
          <div className="divide-y">
            {linkedDocuments.items.map((docItem) => {
              const cfg = DOC_STATUS_MAP[docItem.status] || { label: docItem.status, colorKey: 'draft' }
              return (
                <div key={docItem.id} className="flex items-center gap-3 px-4 py-2.5">
                  <FileText size={15} className="shrink-0 text-muted-foreground" />
                  <Link
                    to="/original-documents/$documentId"
                    params={{ documentId: docItem.id }}
                    className="truncate text-sm text-accent hover:underline"
                  >
                    {docItem.file_name}
                  </Link>
                  <span className="text-xs text-muted-foreground shrink-0">
                    {DOC_TYPE_LABELS[docItem.document_type] || docItem.document_type}
                  </span>
                  {(docItem.total_amount || docItem.amount) && (
                    <span className="text-xs font-mono text-muted-foreground shrink-0">
                      ¥{parseFloat(docItem.total_amount || docItem.amount || '0').toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                    </span>
                  )}
                  <span className="ml-auto shrink-0">
                    <StatusBadge status={cfg.colorKey} label={cfg.label} />
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Audit Actions */}
      <div className="flex items-center justify-between">
        <div />

        <div className="flex gap-3">
          {/* Draft: show Audit + Reject buttons */}
          {canAudit && voucher.status === 'draft' && (
            <>
              <button
                type="button"
                onClick={() => setShowRejectDialog(true)}
                disabled={auditMutation.isPending}
                className="flex items-center gap-1.5 rounded-md border border-red-300 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100 disabled:opacity-50 transition-colors"
              >
                <XCircle size={16} />
                驳回
              </button>
              <button
                type="button"
                onClick={handleAudit}
                disabled={auditMutation.isPending}
                className="flex items-center gap-1.5 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-600/90 disabled:opacity-50 transition-colors"
              >
                <CheckCircle size={16} />
                {auditMutation.isPending ? '审核中...' : '审核通过'}
              </button>
            </>
          )}

          {/* Audited: show Unaudit button */}
          {canUnaudit && voucher.status === 'audited' && (
            <button
              type="button"
              onClick={handleUnaudit}
              disabled={unauditMutation.isPending}
              className="flex items-center gap-1.5 rounded-md border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 hover:bg-amber-100 disabled:opacity-50 transition-colors"
            >
              <Undo2 size={16} />
              {unauditMutation.isPending ? '反审核中...' : '反审核'}
            </button>
          )}
        </div>
      </div>

      {/* Reject Dialog */}
      <RejectDialog
        open={showRejectDialog}
        onConfirm={handleRejectConfirm}
        onCancel={() => setShowRejectDialog(false)}
      />

      {/* Audit mutation error */}
      {auditMutation.isError && (
        <div className="mt-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
          {(auditMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '审核操作失败'}
        </div>
      )}

      {/* Unaudit mutation error */}
      {unauditMutation.isError && (
        <div className="mt-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
          {(unauditMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '反审核操作失败'}
        </div>
      )}
    </div>
  )
}
