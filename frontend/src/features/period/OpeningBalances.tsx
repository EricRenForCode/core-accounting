import { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { AmountInput } from '@/components/AmountInput'
import { Skeleton } from '@/components/Skeleton'
import { ErrorCard } from '@/components/ErrorCard'
import { usePermission } from '@/hooks/usePermission'
import { CheckCircle, AlertTriangle, Save, Lock } from 'lucide-react'
import type { Period } from '@/types/period'

interface OpeningBalanceRow {
  account_id: string
  code: string
  name: string
  dc_type: string
  is_leaf: boolean
  opening_debit: string
  opening_credit: string
}

interface OpeningBalancesResponse {
  period: Period
  editable: boolean
  rows: OpeningBalanceRow[]
  total_debit: string
  total_credit: string
  is_balanced: boolean
}

// Local edit state: account_id -> { debit, credit } as cents-style strings
type EditState = Record<string, { debit: string; credit: string }>

function toNum(v: string): number {
  const n = parseFloat(v)
  return isNaN(n) ? 0 : n
}

function fmt(n: number): string {
  return n.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export default function OpeningBalances() {
  const queryClient = useQueryClient()
  const { can } = usePermission()
  const canManage = can('account:manage')

  const [periodId, setPeriodId] = useState('')
  const [edits, setEdits] = useState<EditState>({})
  const [saveError, setSaveError] = useState('')
  const [saved, setSaved] = useState(false)

  // 1. Load periods for the selector
  const { data: periodsData } = useQuery<{ periods: Period[] }>({
    queryKey: ['periods'],
    queryFn: async () => (await api.get('/periods')).data,
  })
  const periods = periodsData?.periods || []

  // Default to the earliest open period (where opening balances are entered)
  useEffect(() => {
    if (!periodId && periods.length > 0) {
      const open = [...periods]
        .filter((p) => p.status === 'open')
        .sort((a, b) => a.year - b.year || a.month - b.month)
      setPeriodId((open[0] || periods[0]).id)
    }
  }, [periods, periodId])

  // 2. Load opening balances for the selected period
  const { data, isLoading, isError } = useQuery<OpeningBalancesResponse>({
    queryKey: ['opening-balances', periodId],
    queryFn: async () =>
      (await api.get(`/periods/${periodId}/opening-balances`)).data,
    enabled: !!periodId,
  })

  // Seed local edit state whenever fresh data arrives
  useEffect(() => {
    if (!data) return
    const next: EditState = {}
    for (const r of data.rows) {
      if (r.is_leaf) {
        next[r.account_id] = {
          debit: toNum(r.opening_debit) ? r.opening_debit : '',
          credit: toNum(r.opening_credit) ? r.opening_credit : '',
        }
      }
    }
    setEdits(next)
    setSaved(false)
    setSaveError('')
  }, [data])

  // 3. Running totals from local edits
  const { totalDebit, totalCredit, isBalanced } = useMemo(() => {
    let d = 0
    let c = 0
    for (const v of Object.values(edits)) {
      d += toNum(v.debit)
      c += toNum(v.credit)
    }
    return {
      totalDebit: d,
      totalCredit: c,
      isBalanced: Math.abs(d - c) < 0.01,
    }
  }, [edits])

  const setSide = (
    accountId: string,
    side: 'debit' | 'credit',
    value: string,
  ) => {
    setSaved(false)
    setEdits((prev) => {
      const row = prev[accountId] || { debit: '', credit: '' }
      // Entering one side clears the other (constraint: one side must be zero).
      const other = side === 'debit' ? 'credit' : 'debit'
      return {
        ...prev,
        [accountId]: { ...row, [side]: value, [other]: value ? '' : row[other] },
      }
    })
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const entries = Object.entries(edits)
        .map(([account_id, v]) => ({
          account_id,
          opening_debit: toNum(v.debit).toFixed(2),
          opening_credit: toNum(v.credit).toFixed(2),
        }))
        .filter((e) => e.opening_debit !== '0.00' || e.opening_credit !== '0.00')
      return (await api.put(`/periods/${periodId}/opening-balances`, { entries }))
        .data
    },
    onSuccess: () => {
      setSaved(true)
      setSaveError('')
      queryClient.invalidateQueries({ queryKey: ['opening-balances', periodId] })
      queryClient.invalidateQueries({ queryKey: ['trial-balance'] })
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || '保存失败'
      setSaveError(detail)
    },
  })

  const editable = !!data?.editable && canManage

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold">期初余额录入</h1>
          <p className="text-sm text-muted-foreground mt-1">
            新建账套时录入各末级科目的期初余额，借贷合计须平衡
          </p>
        </div>
        <select
          value={periodId}
          onChange={(e) => setPeriodId(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
        >
          {periods.map((p) => (
            <option key={p.id} value={p.id}>
              {p.year}年{String(p.month).padStart(2, '0')}月
              {p.status === 'closed' ? '（已结账）' : ''}
            </option>
          ))}
        </select>
      </div>

      {/* Not editable notice */}
      {data && !data.editable && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
          <Lock size={16} />
          该期间已结账或已有记账凭证，期初余额只读，不可修改。
        </div>
      )}

      {isLoading && (
        <div className="space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {isError && (
        <ErrorCard title="加载期初余额失败" message="请检查会计期间设置" />
      )}

      {data && !isLoading && (
        <>
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-muted-foreground text-xs">
                  <th className="py-2 pl-4 text-left">科目编码</th>
                  <th className="py-2 text-left">科目名称</th>
                  <th className="py-2 pr-3 text-right w-40">期初借方</th>
                  <th className="py-2 pr-4 text-right w-40">期初贷方</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => {
                  const e = edits[r.account_id] || { debit: '', credit: '' }
                  return (
                    <tr
                      key={r.account_id}
                      className="border-b last:border-0 hover:bg-muted/20"
                    >
                      <td className="py-1.5 pl-4 font-mono text-xs text-muted-foreground">
                        {r.code}
                      </td>
                      <td className="py-1.5">
                        {r.name}
                        {!r.is_leaf && (
                          <span className="ml-2 text-xs text-muted-foreground">
                            （汇总科目）
                          </span>
                        )}
                      </td>
                      {r.is_leaf ? (
                        <>
                          <td className="py-1 pr-3">
                            <AmountInput
                              value={e.debit}
                              onChange={(v) => setSide(r.account_id, 'debit', v)}
                              disabled={!editable}
                            />
                          </td>
                          <td className="py-1 pr-4">
                            <AmountInput
                              value={e.credit}
                              onChange={(v) =>
                                setSide(r.account_id, 'credit', v)
                              }
                              disabled={!editable}
                            />
                          </td>
                        </>
                      ) : (
                        <td
                          className="py-1.5 pr-4 text-right text-xs text-muted-foreground"
                          colSpan={2}
                        >
                          由下级汇总
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Totals + balance */}
          <div className="mt-4 flex items-center justify-between">
            <div
              className={`flex items-center gap-1.5 text-sm ${
                isBalanced ? 'text-green-600' : 'text-red-600'
              }`}
            >
              {isBalanced ? (
                <CheckCircle size={16} />
              ) : (
                <AlertTriangle size={16} />
              )}
              {isBalanced
                ? '借贷平衡'
                : `不平衡，差额 ${fmt(Math.abs(totalDebit - totalCredit))}`}
            </div>
            <div className="flex items-center gap-6 text-sm">
              <span>
                借方合计{' '}
                <span className="font-mono font-medium">{fmt(totalDebit)}</span>
              </span>
              <span>
                贷方合计{' '}
                <span className="font-mono font-medium">{fmt(totalCredit)}</span>
              </span>
            </div>
          </div>

          {saveError && (
            <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">
              {saveError}
            </div>
          )}
          {saved && (
            <div className="mt-3 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
              期初余额已保存
            </div>
          )}

          {/* Save */}
          <div className="mt-4 flex justify-end">
            <button
              onClick={() => saveMutation.mutate()}
              disabled={!editable || !isBalanced || saveMutation.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save size={16} />
              {saveMutation.isPending ? '保存中...' : '保存期初余额'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
