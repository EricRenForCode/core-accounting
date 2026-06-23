import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'
import { CheckCircle, XCircle } from 'lucide-react'

interface ReconData {
  matched: Array<{ bank_entry_id: string; voucher_entry_id: string; date: string; amount: string; description: string }>
  bank_only: Array<{ id: string; date: string; amount: string; summary: string; counterparty: string }>
  voucher_only: Array<{ id: string; date: string; voucher_no: string; amount: string; summary: string }>
  bank_balance: number
  voucher_balance: number
  reconciled_balance: number
}

function fmt(n: number | string): string {
  const val = typeof n === 'string' ? parseFloat(n) : n
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function BankReconcile() {
  const [accountId, setAccountId] = useState('')
  const [periodId, setPeriodId] = useState('')
  const [data, setData] = useState<ReconData | null>(null)

  const reconMut = useMutation({
    mutationFn: (body: { account_id: string; period_id: string }) =>
      api.post('/bank-reconcile', body),
    onSuccess: (resp) => setData(resp.data),
  })

  function handleReconcile() {
    reconMut.mutate({ account_id: accountId, period_id: periodId })
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">银行对账</h2>
          <p className="text-sm text-muted-foreground mt-1">将银行流水与企业账务进行自动匹配对账</p>
        </div>
        <div className="flex items-center gap-3">
          <input type="text" value={accountId} onChange={(e) => setAccountId(e.target.value)} className="rounded-md border px-3 py-1.5 text-sm font-mono w-36 focus:outline-none focus:ring-2 focus:ring-accent" placeholder="银行科目ID" />
          <input type="text" value={periodId} onChange={(e) => setPeriodId(e.target.value)} className="rounded-md border px-3 py-1.5 text-sm font-mono w-36 focus:outline-none focus:ring-2 focus:ring-accent" placeholder="期间ID" />
          <button onClick={handleReconcile} disabled={!accountId || !periodId || reconMut.isPending} className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50">
            {reconMut.isPending ? '对账中...' : '开始对账'}
          </button>
        </div>
      </div>

      {!data && !reconMut.isPending && (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          <p className="text-lg">请输入银行科目ID和期间ID开始对账</p>
        </div>
      )}

      {reconMut.isPending && <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">对账中...</div>}

      {data && (
        <>
          {/* Balance Summary */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            {[
              { label: '银行余额', value: data.bank_balance },
              { label: '企业余额', value: data.voucher_balance },
              { label: '差额', value: data.reconciled_balance },
            ].map((item) => (
              <div key={item.label} className="rounded-lg border bg-card p-4">
                <p className="text-sm text-muted-foreground">{item.label}</p>
                <p className={`text-2xl font-bold font-mono mt-1 ${Math.abs(item.value) < 0.01 ? 'text-green-600' : 'text-red-600'}`}>
                  {fmt(item.value)}
                </p>
              </div>
            ))}
          </div>

          {/* Matched */}
          <div className="rounded-lg border bg-card overflow-hidden mb-6">
            <div className="px-4 py-3 bg-green-50 border-b flex items-center gap-2">
              <CheckCircle size={16} className="text-green-600" />
              <span className="font-medium text-green-700">匹配成功 ({data.matched.length} 笔)</span>
            </div>
            {data.matched.length > 0 ? (
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">日期</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">描述</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">金额</th>
                  </tr>
                </thead>
                <tbody>
                  {data.matched.map((m, i) => (
                    <tr key={i} className="border-b">
                      <td className="px-3 py-2 text-sm">{m.date}</td>
                      <td className="px-3 py-2 text-sm">{m.description}</td>
                      <td className="px-3 py-2 text-right text-sm font-mono">{fmt(m.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <div className="p-4 text-sm text-muted-foreground">无匹配项</div>}
          </div>

          {/* Unmatched: Bank only */}
          <div className="rounded-lg border bg-card overflow-hidden mb-6">
            <div className="px-4 py-3 bg-yellow-50 border-b flex items-center gap-2">
              <XCircle size={16} className="text-yellow-600" />
              <span className="font-medium text-yellow-700">银行已记 企业未记 ({data.bank_only.length} 笔)</span>
            </div>
            {data.bank_only.length > 0 && (
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">日期</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">摘要</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">对方</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">金额</th>
                  </tr>
                </thead>
                <tbody>
                  {data.bank_only.map((b, i) => (
                    <tr key={i} className="border-b">
                      <td className="px-3 py-2 text-sm">{b.date}</td>
                      <td className="px-3 py-2 text-sm">{b.summary}</td>
                      <td className="px-3 py-2 text-sm text-muted-foreground">{b.counterparty}</td>
                      <td className="px-3 py-2 text-right text-sm font-mono">{fmt(b.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Unmatched: Voucher only */}
          <div className="rounded-lg border bg-card overflow-hidden">
            <div className="px-4 py-3 bg-blue-50 border-b flex items-center gap-2">
              <XCircle size={16} className="text-blue-600" />
              <span className="font-medium text-blue-700">企业已记 银行未记 ({data.voucher_only.length} 笔)</span>
            </div>
            {data.voucher_only.length > 0 && (
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">日期</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">凭证号</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">摘要</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">金额</th>
                  </tr>
                </thead>
                <tbody>
                  {data.voucher_only.map((v, i) => (
                    <tr key={i} className="border-b">
                      <td className="px-3 py-2 text-sm">{v.date}</td>
                      <td className="px-3 py-2 text-sm font-mono text-accent">{v.voucher_no}</td>
                      <td className="px-3 py-2 text-sm">{v.summary}</td>
                      <td className="px-3 py-2 text-right text-sm font-mono">{fmt(v.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  )
}
