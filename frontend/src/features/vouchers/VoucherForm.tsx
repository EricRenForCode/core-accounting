import { useState, useEffect, useCallback, Fragment } from 'react'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { AccountPicker, type SelectedAccount } from '@/components/AccountPicker'
import { AuxPicker } from '@/components/AuxPicker'
import { AmountInput } from '@/components/AmountInput'
import { BalanceBar } from '@/components/BalanceBar'
import { Plus, Trash2, ArrowUpDown } from 'lucide-react'
import type { AuxTypeValue } from '@/lib/constants'

interface AuxiliaryRef {
  aux_type: string
  aux_entity_id: string
  aux_entity_name: string
}

interface EntryRow {
  id: string
  accountId: string
  accountCode?: string
  accountName?: string
  auxTypes: string[]
  summary: string
  debitAmount: string
  creditAmount: string
  auxiliaries: AuxiliaryRef[]
}

function generateRowId(): string {
  return `entry-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function emptyRow(): EntryRow {
  return {
    id: generateRowId(),
    accountId: '',
    accountCode: '',
    accountName: '',
    auxTypes: [],
    summary: '',
    debitAmount: '',
    creditAmount: '',
    auxiliaries: [],
  }
}

interface CurrentPeriod {
  id: string
  year: number
  month: number
  status: string
}

export default function VoucherForm() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const search = useSearch({ strict: false }) as { templateId?: string }
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [attachments, setAttachments] = useState(0)
  const [entries, setEntries] = useState<EntryRow[]>([emptyRow(), emptyRow()])
  const [currentPeriod, setCurrentPeriod] = useState<CurrentPeriod | null>(null)
  const [periodLoading, setPeriodLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastSummary, setLastSummary] = useState('')

  // Fetch current period
  useEffect(() => {
    api.get('/periods/current')
      .then(({ data }) => {
        setCurrentPeriod(data)
        // Set date to first day of current period if within
        const today = new Date()
        const periodStart = new Date(data.year, data.month - 1, 1)
        const periodEnd = new Date(data.year, data.month, 0)
        if (today >= periodStart && today <= periodEnd) {
          setDate(today.toISOString().slice(0, 10))
        }
      })
      .catch(() => { /* no period open */ })
      .finally(() => setPeriodLoading(false))
  }, [])

  // Prefill entries from a voucher template (模板生成凭证 — P6)
  useEffect(() => {
    const templateId = search?.templateId
    if (!templateId) return
    Promise.all([
      api.get(`/voucher-templates/${templateId}`),
      api.get('/accounts', { params: { page_size: 500, is_enabled: true } }),
    ])
      .then(([tRes, aRes]) => {
        const byId = new Map<string, { code: string; name: string; aux_types: string[] | null }>(
          (aRes.data.accounts ?? []).map(
            (a: { id: string; code: string; name: string; aux_types: string[] | null }) => [a.id, a],
          ),
        )
        const rows: EntryRow[] = (tRes.data.entries ?? []).map(
          (e: { account_id: string; summary?: string; dc_side?: string }) => {
            const acct = byId.get(e.account_id)
            return {
              ...emptyRow(),
              accountId: e.account_id,
              accountCode: acct?.code ?? '',
              accountName: acct?.name ?? '',
              auxTypes: acct?.aux_types ?? [],
              summary: e.summary ?? '',
              // Amounts intentionally left blank — the template fixes the
              // structure (accounts + direction); the user fills amounts.
            }
          },
        )
        if (rows.length > 0) {
          setEntries(rows.length >= 2 ? rows : [...rows, emptyRow()])
        }
      })
      .catch(() => setError('模板加载失败，已打开空白凭证'))
  }, [search?.templateId])

  // Calculate totals
  const totalDebit = entries.reduce((sum, e) => sum + (parseFloat(e.debitAmount) || 0), 0)
  const totalCredit = entries.reduce((sum, e) => sum + (parseFloat(e.creditAmount) || 0), 0)
  const isBalanced = entries.length >= 2 && Math.abs(totalDebit - totalCredit) < 0.01 && totalDebit > 0

  // Create voucher mutation
  const createMutation = useMutation({
    mutationFn: async (data: {
      date: string
      period_id: string
      attachments: number
      entries: Array<{
        row_number: number
        account_id: string
        summary: string
        debit_amount: string
        credit_amount: string
        auxiliaries: Array<{ aux_type: string; aux_entity_id: string }>
      }>
    }) => {
      const { data: result } = await api.post('/vouchers', data)
      return result
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vouchers'] })
      navigate({ to: '/vouchers', params: {} })
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '创建凭证失败'
      setError(msg)
    },
  })

  // Handlers
  const addRow = useCallback(() => {
    setEntries((prev) => [...prev, emptyRow()])
  }, [])

  const removeRow = useCallback((rowId: string) => {
    setEntries((prev) => {
      if (prev.length <= 2) return prev // minimum 2 rows
      return prev.filter((e) => e.id !== rowId)
    })
  }, [])

  const updateRow = useCallback((rowId: string, field: keyof EntryRow, value: string) => {
    setEntries((prev) =>
      prev.map((e) => {
        if (e.id !== rowId) return e
        const updated = { ...e, [field]: value }

        // Auto-clear credit when debit entered, and vice versa
        if (field === 'debitAmount' && value && value !== '0') {
          updated.creditAmount = ''
        }
        if (field === 'creditAmount' && value && value !== '0') {
          updated.debitAmount = ''
        }

        if (field === 'summary' && value) {
          setLastSummary(value)
        }

        return updated
      }),
    )
  }, [])

  const handleAccountSelect = useCallback((rowId: string, account: SelectedAccount) => {
    setEntries((prev) =>
      prev.map((e) =>
        e.id === rowId
          ? {
              ...e,
              accountId: account.id,
              accountCode: account.code,
              accountName: account.name,
              auxTypes: account.aux_types || [],
              auxiliaries: [], // Reset auxiliaries when account changes
            }
          : e,
      ),
    )
  }, [])

  const duplicateRow = useCallback((rowId: string) => {
    setEntries((prev) => {
      const idx = prev.findIndex((e) => e.id === rowId)
      if (idx === -1) return prev
      const source = prev[idx]
      const dup: EntryRow = {
        ...source,
        id: generateRowId(),
        debitAmount: source.creditAmount,
        creditAmount: source.debitAmount,
        auxiliaries: [...source.auxiliaries],
      }
      const next = [...prev]
      next.splice(idx + 1, 0, dup)
      return next
    })
  }, [])

  const handleSubmit = (_saveAsDraft: boolean) => {
    setError('')

    if (!currentPeriod) {
      setError('当前没有打开的会计期间')
      return
    }

    // Validate entries
    const validEntries = entries.filter(
      (e) => e.accountId && e.summary.trim() && (parseFloat(e.debitAmount) > 0 || parseFloat(e.creditAmount) > 0),
    )

    if (validEntries.length < 2) {
      setError('至少需要2行有效分录')
      return
    }

    if (entries.some((e) => !e.accountId)) {
      setError('请为所有分录选择科目')
      return
    }

    if (entries.some((e) => !e.summary.trim())) {
      setError('请为所有分录填写摘要')
      return
    }

    if (!isBalanced) {
      setError('凭证借贷不平衡，请检查金额')
      return
    }

    const body = {
      date,
      period_id: currentPeriod.id,
      attachments,
      entries: validEntries.map((e, i) => ({
        row_number: i + 1,
        account_id: e.accountId,
        summary: e.summary.trim(),
        debit_amount: e.debitAmount || '0',
        credit_amount: e.creditAmount || '0',
        auxiliaries: e.auxiliaries.map((a) => ({
          aux_type: a.aux_type,
          aux_entity_id: a.aux_entity_id,
        })),
      })),
    }

    createMutation.mutate(body)
  }

  // Keyboard shortcut: Ctrl+Enter to save
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        handleSubmit(true)
      }
      // Ctrl+N to add row
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault()
        addRow()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [entries, date, attachments, currentPeriod, isBalanced])

  if (periodLoading) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          加载中...
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold mb-1">录入凭证</h2>
      <p className="text-sm text-muted-foreground mb-6">
        {currentPeriod
          ? `当前期间: ${currentPeriod.year}年${currentPeriod.month}月`
          : '⚠️ 当前没有打开的会计期间'}
      </p>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Header */}
      <div className="rounded-lg border bg-card mb-4">
        <div className="p-4 flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">凭证日期</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              min={currentPeriod ? `${currentPeriod.year}-${String(currentPeriod.month).padStart(2, '0')}-01` : undefined}
              max={currentPeriod ? `${currentPeriod.year}-${String(currentPeriod.month).padStart(2, '0')}-${new Date(currentPeriod.year, currentPeriod.month, 0).getDate()}` : undefined}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">附单据数</label>
            <input
              type="number"
              min={0}
              value={attachments}
              onChange={(e) => setAttachments(parseInt(e.target.value) || 0)}
              className="w-24 rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent text-right"
            />
          </div>
          <div className="ml-auto text-xs text-muted-foreground">
            <kbd className="rounded border px-1 py-0.5 text-xs">Ctrl+N</kbd> 新增行
            {' · '}
            <kbd className="rounded border px-1 py-0.5 text-xs">Ctrl+Enter</kbd> 保存
          </div>
        </div>
      </div>

      {/* Entry table */}
      <div className="rounded-lg border bg-card mb-4 overflow-hidden">
        <div className="overflow-auto max-h-[45vh]">
          <table className="w-full">
            <thead className="sticky top-0 z-10 [&_th]:bg-gray-50">
              <tr className="border-b bg-gray-50">
                <th className="w-10 px-3 py-2 text-center text-xs font-medium text-muted-foreground">#</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">科目</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground" style={{ minWidth: 200 }}>摘要</th>
                <th className="w-36 px-3 py-2 text-right text-xs font-medium text-muted-foreground">借方金额</th>
                <th className="w-36 px-3 py-2 text-right text-xs font-medium text-muted-foreground">贷方金额</th>
                <th className="w-20 px-3 py-2 text-center text-xs font-medium text-muted-foreground">操作</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, idx) => (
                <Fragment key={entry.id}>
                  <tr className="border-b last:border-b-0 hover:bg-gray-50/50">
                    <td className="px-3 py-2 text-center text-sm text-muted-foreground font-mono">
                      {idx + 1}
                    </td>
                    <td className="px-1 py-1" style={{ minWidth: 220 }}>
                      <AccountPicker
                        value={entry.accountId}
                        onChange={(account) => handleAccountSelect(entry.id, account)}
                        placeholder="选择科目..."
                      />
                    </td>
                    <td className="px-1 py-1">
                      <input
                        type="text"
                        value={entry.summary}
                        onChange={(e) => updateRow(entry.id, 'summary', e.target.value)}
                        placeholder={lastSummary || '请输入摘要'}
                        className="w-full rounded border px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
                      />
                    </td>
                    <td className="px-1 py-1">
                      <AmountInput
                        value={entry.debitAmount}
                        onChange={(v) => updateRow(entry.id, 'debitAmount', v)}
                        placeholder="0.00"
                        disabled={!!entry.creditAmount && parseFloat(entry.creditAmount) > 0}
                      />
                    </td>
                    <td className="px-1 py-1">
                      <AmountInput
                        value={entry.creditAmount}
                        onChange={(v) => updateRow(entry.id, 'creditAmount', v)}
                        placeholder="0.00"
                        disabled={!!entry.debitAmount && parseFloat(entry.debitAmount) > 0}
                      />
                    </td>
                    <td className="px-1 py-1">
                      <div className="flex items-center justify-center gap-0.5">
                        <button
                          type="button"
                          onClick={() => duplicateRow(entry.id)}
                          className="p-1 rounded hover:bg-gray-200 text-muted-foreground hover:text-foreground"
                          title="复制并取反"
                        >
                          <ArrowUpDown size={14} />
                        </button>
                        <button
                          type="button"
                          onClick={() => removeRow(entry.id)}
                          disabled={entries.length <= 2}
                          className="p-1 rounded hover:bg-red-100 text-muted-foreground hover:text-red-600 disabled:opacity-30 disabled:cursor-not-allowed"
                          title="删除行"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {/* Auxiliary核算 row */}
                  {entry.accountId && entry.auxTypes.length > 0 && (
                    <tr key={`${entry.id}-aux`}>
                      <td />
                      <td colSpan={5} className="px-3 py-1.5">
                        <div className="flex flex-wrap gap-2">
                          <span className="text-xs text-muted-foreground self-center">辅助核算:</span>
                          {entry.auxTypes.map((auxType) => {
                            const existingAux = entry.auxiliaries.find((a) => a.aux_type === auxType)
                            return (
                              <div key={auxType} className="flex items-center gap-1">
                                <span className="text-xs font-medium text-muted-foreground min-w-[32px]">
                                  {auxType}
                                </span>
                                <AuxPicker
                                  auxType={auxType as AuxTypeValue}
                                  value={existingAux?.aux_entity_id || ''}
                                  onChange={(entityId, entityName) => {
                                    setEntries((prev) =>
                                      prev.map((e) => {
                                        if (e.id !== entry.id) return e
                                        const otherAux = e.auxiliaries.filter(
                                          (a) => a.aux_type !== auxType,
                                        )
                                        return {
                                          ...e,
                                          auxiliaries: [
                                            ...otherAux,
                                            {
                                              aux_type: auxType,
                                              aux_entity_id: entityId,
                                              aux_entity_name: entityName,
                                            },
                                          ],
                                        }
                                      }),
                                    )
                                  }}
                                  className="w-48"
                                />
                              </div>
                            )
                          })}
                        </div>
                      </td>
                      <td />
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>

        {/* Add row button */}
        <div className="border-t px-3 py-2">
          <button
            type="button"
            onClick={addRow}
            className="flex items-center gap-1 text-sm text-accent hover:text-accent/80"
          >
            <Plus size={16} />
            添加分录行
          </button>
        </div>
      </div>

      {/* Balance bar */}
      <div className="mb-4">
        <BalanceBar totalDebit={totalDebit} totalCredit={totalCredit} />
      </div>

      {/* Action buttons */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate({ to: '/vouchers' })}
          className="rounded-md border px-4 py-2 text-sm text-muted-foreground hover:bg-gray-50"
        >
          取消
        </button>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => handleSubmit(true)}
            disabled={createMutation.isPending || !currentPeriod}
            className="rounded-md border border-accent px-6 py-2 text-sm text-accent font-medium hover:bg-accent/5 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {createMutation.isPending ? '保存中...' : '保存草稿'}
          </button>
          <button
            type="button"
            onClick={() => handleSubmit(false)}
            disabled={createMutation.isPending || !isBalanced || !currentPeriod}
            className="rounded-md bg-accent px-6 py-2 text-sm text-white font-medium hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {createMutation.isPending ? '提交中...' : '提交审核'}
          </button>
        </div>
      </div>
    </div>
  )
}
