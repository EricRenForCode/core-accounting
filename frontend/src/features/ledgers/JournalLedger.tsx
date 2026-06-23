import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { Download } from 'lucide-react'

interface JournalRow {
  date: string
  voucher_no: string
  account_code: string
  account_name: string
  summary: string
  debit: number
  credit: number
}

interface JournalData {
  period: { year: number; month: number }
  rows: JournalRow[]
  total_debit: number
  total_credit: number
}

function fmt(n: number | string): string {
  const val = typeof n === 'string' ? parseFloat(n) : n
  if (val === 0) return ''
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function JournalLedger() {
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const periodId = 'current'

  const { data, isLoading, isError } = useQuery<JournalData>({
    queryKey: ['journal', periodId, dateFrom, dateTo],
    queryFn: async () => {
      const params: Record<string, string> = { period_id: periodId }
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      const { data } = await api.get<JournalData>('/reports/journal', { params })
      return data
    },
    enabled: periodId !== 'current',
  })

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">序时账</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.period
              ? `${data.period.year}年${data.period.month}月`
              : '加载中...'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            placeholder="开始日期"
          />
          <span className="text-sm text-muted-foreground">至</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            placeholder="结束日期"
          />
          <button className="flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm hover:bg-gray-50 transition-colors">
            <Download size={14} />
            导出
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          加载中...
        </div>
      )}

      {isError && (
        <div className="rounded-lg border bg-red-50 p-8 text-center">
          <p className="text-red-600 font-medium">加载序时账失败</p>
        </div>
      )}

      {data && data.rows.length === 0 && (
        <div className="rounded-lg border bg-card p-12 text-center">
          <p className="text-lg text-muted-foreground">暂无凭证记录</p>
        </div>
      )}

      {data && data.rows.length > 0 && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">日期</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">凭证号</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">科目编码</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">科目名称</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">摘要</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">借方金额</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">贷方金额</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, idx) => (
                  <tr key={idx} className="border-b hover:bg-gray-50/50">
                    <td className="px-3 py-2 text-sm">{row.date}</td>
                    <td className="px-3 py-2 text-sm font-mono text-accent">{row.voucher_no}</td>
                    <td className="px-3 py-2 text-sm font-mono text-xs text-muted-foreground">{row.account_code}</td>
                    <td className="px-3 py-2 text-sm">{row.account_name}</td>
                    <td className="px-3 py-2 text-sm">{row.summary}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono">{fmt(row.debit)}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono">{fmt(row.credit)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 bg-gray-100 font-bold">
                  <td className="px-3 py-2 text-sm" colSpan={5}>合计</td>
                  <td className="px-3 py-2 text-right text-sm font-mono">{fmt(data.total_debit)}</td>
                  <td className="px-3 py-2 text-right text-sm font-mono">{fmt(data.total_credit)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
