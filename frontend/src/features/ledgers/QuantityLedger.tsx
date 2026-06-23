import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

interface QuantityLedgerRow {
  date: string
  voucher_no: string
  summary: string
  quantity_in: number
  amount_in: number
  quantity_out: number
  amount_out: number
  quantity_balance: number
  amount_balance: number
}

interface QuantityLedgerData {
  period: { year: number; month: number }
  account: { id: string; code: string; name: string }
  unit: string
  opening_quantity: number
  opening_amount: number
  rows: QuantityLedgerRow[]
  closing_quantity: number
  closing_amount: number
}

function fmt(n: number | string): string {
  const val = typeof n === 'string' ? parseFloat(n) : n
  if (!val || val === 0) return ''
  return val.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function fmtQty(n: number | string): string {
  const val = typeof n === 'string' ? parseFloat(n) : n
  if (!val || val === 0) return ''
  return val.toLocaleString('zh-CN', {
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  })
}

export default function QuantityLedger() {
  const [accountId, setAccountId] = useState('')
  const [periodId, setPeriodId] = useState('')

  const { data, isLoading, isError, error } = useQuery<QuantityLedgerData>({
    queryKey: ['quantity-ledger', accountId, periodId],
    queryFn: async () => {
      const { data } = await api.get<QuantityLedgerData>(
        `/reports/quantity-ledger/${accountId}`,
        { params: { period_id: periodId } },
      )
      return data
    },
    enabled: !!accountId && !!periodId,
  })

  const errorMessage = useMemo(() => {
    if (!error) return null
    const err = error as { response?: { data?: { detail?: string } } }
    return err?.response?.data?.detail || '加载数量金额账失败'
  }, [error])

  // Compute totals for footer
  const totals = useMemo(() => {
    if (!data?.rows) return null
    return data.rows.reduce(
      (acc, r) => ({
        quantity_in: acc.quantity_in + (r.quantity_in || 0),
        amount_in: acc.amount_in + (r.amount_in || 0),
        quantity_out: acc.quantity_out + (r.quantity_out || 0),
        amount_out: acc.amount_out + (r.amount_out || 0),
      }),
      { quantity_in: 0, amount_in: 0, quantity_out: 0, amount_out: 0 },
    )
  }, [data])

  return (
    <div className="p-6 max-w-full mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">数量金额账</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.account && `${data.account.code} ${data.account.name}`}
            {data?.period &&
              ` — ${data.period.year}年${data.period.month}月`}
            {data?.unit && ` (单位: ${data.unit})`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent w-48"
            placeholder="科目ID（数量核算）"
          />
          <input
            type="text"
            value={periodId}
            onChange={(e) => setPeriodId(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent w-48"
            placeholder="期间ID"
          />
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
          <p className="text-sm text-red-500 mt-1">
            请确认科目已启用数量核算且会计期间有效
          </p>
        </div>
      )}

      {/* Placeholder / Empty */}
      {!accountId || !periodId ? (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          <p className="text-lg">请输入科目ID和期间ID查询数量金额账</p>
          <p className="text-sm mt-2">
            仅适用于启用数量核算的科目（如原材料、库存商品等）
          </p>
        </div>
      ) : data && data.rows.length === 0 ? (
        <div className="rounded-lg border bg-card p-12 text-center">
          <p className="text-lg text-muted-foreground">暂无数据</p>
          <p className="text-sm text-muted-foreground mt-1">
            该科目在所选期间内尚无已记账凭证
          </p>
        </div>
      ) : null}

      {/* Table */}
      {data && data.rows.length > 0 && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">
                    日期
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">
                    凭证号
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">
                    摘要
                  </th>
                  <th
                    className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground"
                    colSpan={3}
                  >
                    借方（收入）
                  </th>
                  <th
                    className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground"
                    colSpan={3}
                  >
                    贷方（发出）
                  </th>
                  <th
                    className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground"
                    colSpan={2}
                  >
                    余额
                  </th>
                </tr>
                <tr className="border-b bg-gray-50">
                  <th />
                  <th />
                  <th />
                  <th className="px-2 py-1 text-right text-[10px] font-medium text-muted-foreground">
                    数量
                  </th>
                  <th className="px-2 py-1 text-right text-[10px] font-medium text-muted-foreground">
                    单价
                  </th>
                  <th className="px-2 py-1 text-right text-[10px] font-medium text-muted-foreground">
                    金额
                  </th>
                  <th className="px-2 py-1 text-right text-[10px] font-medium text-muted-foreground">
                    数量
                  </th>
                  <th className="px-2 py-1 text-right text-[10px] font-medium text-muted-foreground">
                    单价
                  </th>
                  <th className="px-2 py-1 text-right text-[10px] font-medium text-muted-foreground">
                    金额
                  </th>
                  <th className="px-2 py-1 text-right text-[10px] font-medium text-muted-foreground">
                    数量
                  </th>
                  <th className="px-2 py-1 text-right text-[10px] font-medium text-muted-foreground">
                    金额
                  </th>
                </tr>
              </thead>
              <tbody>
                {/* Opening balance row */}
                <tr className="border-b bg-gray-50/50 text-sm text-muted-foreground">
                  <td className="px-3 py-2" colSpan={3}>
                    期初余额
                  </td>
                  <td className="px-2 py-2" colSpan={3} />
                  <td className="px-2 py-2" colSpan={3} />
                  <td className="px-2 py-2 text-right font-mono">
                    {fmtQty(data.opening_quantity)}
                  </td>
                  <td className="px-2 py-2 text-right font-mono">
                    {fmt(data.opening_amount)}
                  </td>
                </tr>

                {/* Detail rows */}
                {data.rows.map((row, idx) => (
                  <tr
                    key={idx}
                    className="border-b hover:bg-gray-50/50 transition-colors"
                  >
                    <td className="px-3 py-2 text-sm whitespace-nowrap">
                      {row.date}
                    </td>
                    <td className="px-3 py-2 text-sm font-mono text-accent whitespace-nowrap">
                      {row.voucher_no}
                    </td>
                    <td className="px-3 py-2 text-sm max-w-[200px] truncate">
                      {row.summary || '-'}
                    </td>
                    <td className="px-2 py-2 text-right text-sm font-mono">
                      {fmtQty(row.quantity_in)}
                    </td>
                    <td className="px-2 py-2 text-right text-sm text-muted-foreground">
                      {row.quantity_in > 0 && row.amount_in > 0
                        ? (row.amount_in / row.quantity_in).toFixed(4)
                        : ''}
                    </td>
                    <td className="px-2 py-2 text-right text-sm font-mono">
                      {fmt(row.amount_in)}
                    </td>
                    <td className="px-2 py-2 text-right text-sm font-mono">
                      {fmtQty(row.quantity_out)}
                    </td>
                    <td className="px-2 py-2 text-right text-sm text-muted-foreground">
                      {row.quantity_out > 0 && row.amount_out > 0
                        ? (row.amount_out / row.quantity_out).toFixed(4)
                        : ''}
                    </td>
                    <td className="px-2 py-2 text-right text-sm font-mono">
                      {fmt(row.amount_out)}
                    </td>
                    <td className="px-2 py-2 text-right text-sm font-mono font-medium">
                      {fmtQty(row.quantity_balance)}
                    </td>
                    <td className="px-2 py-2 text-right text-sm font-mono font-medium">
                      {fmt(row.amount_balance)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 bg-gray-100 font-bold">
                  <td className="px-3 py-2 text-sm" colSpan={3}>
                    本期合计
                  </td>
                  <td className="px-2 py-2 text-right text-sm font-mono">
                    {fmtQty(totals?.quantity_in || 0)}
                  </td>
                  <td className="px-2 py-2" />
                  <td className="px-2 py-2 text-right text-sm font-mono">
                    {fmt(totals?.amount_in || 0)}
                  </td>
                  <td className="px-2 py-2 text-right text-sm font-mono">
                    {fmtQty(totals?.quantity_out || 0)}
                  </td>
                  <td className="px-2 py-2" />
                  <td className="px-2 py-2 text-right text-sm font-mono">
                    {fmt(totals?.amount_out || 0)}
                  </td>
                  <td className="px-2 py-2" colSpan={2} />
                </tr>
                <tr className="bg-gray-100 font-bold">
                  <td className="px-3 py-2 text-sm" colSpan={3}>
                    期末余额
                  </td>
                  <td className="px-2 py-2" colSpan={6} />
                  <td className="px-2 py-2 text-right text-sm font-mono">
                    {fmtQty(data.closing_quantity)}
                  </td>
                  <td className="px-2 py-2 text-right text-sm font-mono">
                    {fmt(data.closing_amount)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
