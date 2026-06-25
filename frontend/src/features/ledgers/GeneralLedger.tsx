import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { AccountPicker, type SelectedAccount } from '@/components/AccountPicker'
import type { Period } from '@/types/period'

interface GeneralLedgerRow {
  date: string
  voucher_no: string
  summary: string
  debit: number | string
  credit: number | string
  balance_direction: string
  balance: number | string
}

interface GeneralLedgerData {
  period: { year: number; month: number }
  account: { id: string; code: string; name: string }
  opening_balance: number | string
  rows: GeneralLedgerRow[]
  closing_balance: number | string
}

function fmt(n: number | string): string {
  const val = typeof n === 'string' ? parseFloat(n) : n
  if (!val || val === 0) return ''
  return val.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function num(n: number | string): number {
  return typeof n === 'string' ? parseFloat(n) : n
}

export default function GeneralLedger() {
  const [periodId, setPeriodId] = useState('')
  const [account, setAccount] = useState<SelectedAccount | null>(null)

  const { data: periodsData } = useQuery<{ periods: Period[] }>({
    queryKey: ['periods'],
    queryFn: async () => {
      const { data } = await api.get('/periods')
      return data
    },
  })
  const periods = periodsData?.periods || []

  // Default to the most recent period once the list loads
  useEffect(() => {
    if (!periodId && periods.length > 0) {
      setPeriodId(periods[0].id)
    }
  }, [periods, periodId])

  const accountId = account?.id || ''

  const { data, isLoading, isError, error } = useQuery<GeneralLedgerData>({
    queryKey: ['general-ledger', periodId, accountId],
    queryFn: async () => {
      const { data } = await api.get<GeneralLedgerData>('/reports/general-ledger', {
        params: { period_id: periodId, account_id: accountId },
      })
      return data
    },
    enabled: !!periodId && !!accountId,
  })

  const errorMessage = (() => {
    if (!error) return null
    const err = error as { response?: { data?: { detail?: string } } }
    return err?.response?.data?.detail || '加载总账失败'
  })()

  // Total debit/credit for the period
  const totals = data?.rows.reduce(
    (acc, r) => ({ debit: acc.debit + num(r.debit), credit: acc.credit + num(r.credit) }),
    { debit: 0, credit: 0 },
  )

  const openingAbs = data ? Math.abs(num(data.opening_balance)) : 0
  const openingDir = data && num(data.opening_balance) < 0 ? '贷' : '借'

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold">总账</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.account && `${data.account.code} ${data.account.name}`}
            {data?.period && ` — ${data.period.year}年${data.period.month}月`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-64">
            <AccountPicker
              value={account?.id}
              onChange={setAccount}
              filter={(a) => !a.children || a.children.length === 0}
              placeholder="选择科目..."
            />
          </div>
          <select
            value={periodId}
            onChange={(e) => setPeriodId(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          >
            <option value="">选择期间</option>
            {periods.map((p) => (
              <option key={p.id} value={p.id}>
                {p.year}年{p.month}月
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          加载中...
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-lg border bg-red-50 p-8 text-center">
          <p className="text-red-600 font-medium">{errorMessage}</p>
        </div>
      )}

      {/* Empty selection */}
      {!accountId || !periodId ? (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          <p className="text-lg">请选择科目和会计期间查询总账</p>
        </div>
      ) : null}

      {/* Table */}
      {data && accountId && periodId && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">日期</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">凭证号</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">摘要</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">借方</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">贷方</th>
                  <th className="px-3 py-2.5 text-center text-xs font-medium text-muted-foreground">方向</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">余额</th>
                </tr>
              </thead>
              <tbody>
                {/* Opening balance */}
                <tr className="border-b bg-gray-50/50 text-sm text-muted-foreground">
                  <td className="px-3 py-2" colSpan={5}>期初余额</td>
                  <td className="px-3 py-2 text-center font-mono">{openingDir}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(openingAbs)}</td>
                </tr>

                {data.rows.map((row, idx) => (
                  <tr key={idx} className="border-b hover:bg-gray-50/50 transition-colors">
                    <td className="px-3 py-2 text-sm whitespace-nowrap">{row.date}</td>
                    <td className="px-3 py-2 text-sm font-mono text-accent whitespace-nowrap">{row.voucher_no}</td>
                    <td className="px-3 py-2 text-sm max-w-[260px] truncate">{row.summary || '-'}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono">{fmt(row.debit)}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono">{fmt(row.credit)}</td>
                    <td className="px-3 py-2 text-center text-sm font-mono">{row.balance_direction}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono font-medium">{fmt(row.balance)}</td>
                  </tr>
                ))}

                {data.rows.length === 0 && (
                  <tr className="border-b">
                    <td className="px-3 py-6 text-center text-sm text-muted-foreground" colSpan={7}>
                      该科目在所选期间内尚无已记账凭证
                    </td>
                  </tr>
                )}
              </tbody>
              <tfoot>
                <tr className="border-t-2 bg-gray-100 font-bold">
                  <td className="px-3 py-2 text-sm" colSpan={3}>本期合计</td>
                  <td className="px-3 py-2 text-right text-sm font-mono">{fmt(totals?.debit || 0)}</td>
                  <td className="px-3 py-2 text-right text-sm font-mono">{fmt(totals?.credit || 0)}</td>
                  <td className="px-3 py-2" />
                  <td className="px-3 py-2" />
                </tr>
                <tr className="bg-gray-100 font-bold">
                  <td className="px-3 py-2 text-sm" colSpan={6}>期末余额</td>
                  <td className="px-3 py-2 text-right text-sm font-mono">{fmt(data.closing_balance)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
