import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { Upload } from 'lucide-react'

interface BankRow {
  id: string
  date: string
  voucher_no: string | null
  summary: string
  debit: number
  credit: number
  balance: number
  counterparty: string | null
  serial_no: string | null
}

interface BankData {
  account: { id: string; code: string; name: string }
  period: object
  rows: BankRow[]
  total_debit: number
  total_credit: number
  closing_balance: number
}

function fmt(n: number): string {
  if (!n || n === 0) return ''
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function BankJournal() {
  const queryClient = useQueryClient()
  const [accountId, setAccountId] = useState('')
  const [periodId, setPeriodId] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const { data, isLoading, isError } = useQuery<BankData>({
    queryKey: ['bank-journals', accountId, periodId, dateFrom, dateTo],
    queryFn: async () => {
      const params: Record<string, string> = { account_id: accountId }
      if (periodId) params.period_id = periodId
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      const { data } = await api.get<BankData>('/bank-journals', { params })
      return data
    },
    enabled: !!accountId,
  })

  const importMut = useMutation({
    mutationFn: (body: { account_id: string; period_id: string; rows: unknown[] }) =>
      api.post('/bank-journals/import', body),
    onSuccess: (resp) => {
      queryClient.invalidateQueries({ queryKey: ['bank-journals'] })
      alert(`导入成功: ${resp.data.imported} 条`)
    },
    onError: () => alert('导入失败'),
  })

  // Simulated import from a simple JSON textarea
  function handleImport() {
    const json = prompt('请输入银行流水JSON（每行: {date, summary, debit, credit, counterparty, serial_no}）:')
    if (!json) return
    try {
      const rows = JSON.parse(json)
      importMut.mutate({ account_id: accountId, period_id: periodId, rows: Array.isArray(rows) ? rows : [rows] })
    } catch {
      alert('JSON格式错误')
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">银行日记账</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.account && `${data.account.code} ${data.account.name}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input type="text" value={accountId} onChange={(e) => setAccountId(e.target.value)} className="rounded-md border px-3 py-1.5 text-sm font-mono w-36 focus:outline-none focus:ring-2 focus:ring-accent" placeholder="科目ID" />
          <input type="text" value={periodId} onChange={(e) => setPeriodId(e.target.value)} className="rounded-md border px-3 py-1.5 text-sm font-mono w-36 focus:outline-none focus:ring-2 focus:ring-accent" placeholder="期间ID" />
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded-md border px-3 py-1.5 text-sm" />
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded-md border px-3 py-1.5 text-sm" />
          <button onClick={handleImport} className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-gray-50">
            <Upload size={14} />导入流水
          </button>
        </div>
      </div>

      {isLoading && <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">加载中...</div>}
      {isError && <div className="rounded-lg border bg-red-50 p-8 text-center"><p className="text-red-600 font-medium">加载失败</p></div>}
      {!accountId && <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground"><p className="text-lg">请输入科目ID查询银行日记账</p></div>}

      {data && data.rows.length > 0 && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">日期</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">摘要</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">对方单位</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">票据号</th>
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
                    <td className="px-3 py-2 text-sm font-mono text-xs text-muted-foreground">{r.serial_no || '-'}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono">{fmt(r.debit)}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono">{fmt(r.credit)}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono font-medium">{fmt(r.balance)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 bg-gray-100 font-bold">
                  <td className="px-3 py-2 text-sm" colSpan={4}>合计</td>
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
