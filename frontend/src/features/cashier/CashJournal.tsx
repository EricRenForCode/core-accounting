import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { Plus } from 'lucide-react'

interface CashRow {
  id: string
  date: string
  voucher_no: string | null
  summary: string
  debit: number
  credit: number
  balance: number
  counterparty: string | null
}

interface CashData {
  account: { id: string; code: string; name: string }
  period: object
  opening_balance: number
  rows: CashRow[]
  total_debit: number
  total_credit: number
  closing_balance: number
}

function fmt(n: number): string {
  if (!n || n === 0) return ''
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function CashJournal() {
  const queryClient = useQueryClient()
  const [accountId, setAccountId] = useState('')
  const [periodId, setPeriodId] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [formDate, setFormDate] = useState(new Date().toISOString().slice(0, 10))
  const [formSummary, setFormSummary] = useState('')
  const [formDebit, setFormDebit] = useState('')
  const [formCredit, setFormCredit] = useState('')
  const [formParty, setFormParty] = useState('')

  const { data, isLoading, isError } = useQuery<CashData>({
    queryKey: ['cash-journals', accountId, periodId, dateFrom, dateTo],
    queryFn: async () => {
      const params: Record<string, string> = { account_id: accountId }
      if (periodId) params.period_id = periodId
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      const { data } = await api.get<CashData>('/cash-journals', { params })
      return data
    },
    enabled: !!accountId,
  })

  const createMut = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post('/cash-journals', body, { params: { period_id: periodId } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cash-journals'] })
      setShowForm(false)
      setFormSummary('')
      setFormDebit('')
      setFormCredit('')
      setFormParty('')
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!formSummary.trim()) return
    createMut.mutate({
      date: formDate,
      account_id: accountId,
      summary: formSummary.trim(),
      debit: formDebit ? parseFloat(formDebit) : 0,
      credit: formCredit ? parseFloat(formCredit) : 0,
      counterparty: formParty || undefined,
    })
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">现金日记账</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.account && `${data.account.code} ${data.account.name}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm font-mono w-36 focus:outline-none focus:ring-2 focus:ring-accent"
            placeholder="科目ID"
          />
          <input
            type="text"
            value={periodId}
            onChange={(e) => setPeriodId(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm font-mono w-36 focus:outline-none focus:ring-2 focus:ring-accent"
            placeholder="期间ID"
          />
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded-md border px-3 py-1.5 text-sm" />
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded-md border px-3 py-1.5 text-sm" />
          <button onClick={() => setShowForm(true)} className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent/90">
            <Plus size={14} />录入
          </button>
        </div>
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-bold mb-4">录入现金日记账</h3>
            <form onSubmit={handleSubmit} className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">日期</label>
                <input type="date" value={formDate} onChange={(e) => setFormDate(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">摘要</label>
                <input type="text" value={formSummary} onChange={(e) => setFormSummary(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent" placeholder="请输入摘要" maxLength={200} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">借方金额</label>
                  <input type="number" step="0.01" value={formDebit} onChange={(e) => setFormDebit(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent" placeholder="0.00" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">贷方金额</label>
                  <input type="number" step="0.01" value={formCredit} onChange={(e) => setFormCredit(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent" placeholder="0.00" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">对方单位</label>
                <input type="text" value={formParty} onChange={(e) => setFormParty(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent" placeholder="对方单位名称" />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="rounded-md border px-4 py-2 text-sm hover:bg-gray-50">取消</button>
                <button type="submit" className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90">保存</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isLoading && <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">加载中...</div>}
      {isError && <div className="rounded-lg border bg-red-50 p-8 text-center"><p className="text-red-600 font-medium">加载失败</p></div>}
      {!accountId && <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground"><p className="text-lg">请输入科目ID查询现金日记账</p></div>}

      {data && data.rows.length > 0 && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">日期</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">摘要</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">对方单位</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">借方</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">贷方</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">余额</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.id} className="border-b hover:bg-gray-50/50">
                    <td className="px-3 py-2 text-sm">{r.date}</td>
                    <td className="px-3 py-2 text-sm">{r.summary}</td>
                    <td className="px-3 py-2 text-sm text-muted-foreground">{r.counterparty || '-'}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono">{fmt(r.debit)}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono">{fmt(r.credit)}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono font-medium">{fmt(r.balance)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 bg-gray-100 font-bold">
                  <td className="px-3 py-2 text-sm" colSpan={3}>合计</td>
                  <td className="px-3 py-2 text-right text-sm font-mono">{fmt(data.total_debit)}</td>
                  <td className="px-3 py-2 text-right text-sm font-mono">{fmt(data.total_credit)}</td>
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
