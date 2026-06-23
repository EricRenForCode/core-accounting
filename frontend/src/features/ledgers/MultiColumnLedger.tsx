import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'

interface ColumnDef {
  account_code: string
  account_name: string
}

interface MultiColumnRow {
  date: string
  voucher_no: string
  summary: string
  column_values: Record<string, { debit: string; credit: string }>
  total_debit: number
  total_credit: number
}

interface MultiColumnData {
  period: { year: number; month: number }
  account: { id: string; code: string; name: string }
  columns: ColumnDef[]
  rows: MultiColumnRow[]
  total_debit: number
  total_credit: number
}

function fmt(n: number | string): string {
  const val = typeof n === 'string' ? parseFloat(n) : n
  if (!val || val === 0) return ''
  return val.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export default function MultiColumnLedger() {
  const [accountId, setAccountId] = useState('')
  const [periodId, setPeriodId] = useState('')

  const { data, isLoading, isError, error } = useQuery<MultiColumnData>({
    queryKey: ['multi-column-ledger', accountId, periodId],
    queryFn: async () => {
      const { data } = await api.get<MultiColumnData>(
        `/reports/multi-column-ledger/${accountId}`,
        { params: { period_id: periodId } },
      )
      return data
    },
    enabled: !!accountId && !!periodId,
  })

  const errorMessage = useMemo(() => {
    if (!error) return null
    const err = error as { response?: { data?: { detail?: string } } }
    return err?.response?.data?.detail || '加载多栏明细账失败'
  }, [error])

  return (
    <div className="p-6 max-w-full mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">多栏明细账</h2>
          <p className="text-sm text-muted-foreground mt-1">
            按对方科目展开的多栏式明细账
            {data?.period &&
              ` — ${data.period.year}年${data.period.month}月`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent w-48"
            placeholder="科目ID"
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
            请确认科目和会计期间是否存在
          </p>
        </div>
      )}

      {/* Placeholder when no params */}
      {!accountId || !periodId ? (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          <p className="text-lg">请输入科目ID和期间ID查询多栏明细账</p>
          <p className="text-sm mt-2">
            多栏明细账按对方科目展开多栏，显示每个凭证中涉及的所有对方科目金额
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
                {/* Header Row 1: Column groups */}
                <tr className="border-b bg-gray-50">
                  <th
                    className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground"
                    rowSpan={2}
                  >
                    日期
                  </th>
                  <th
                    className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground"
                    rowSpan={2}
                  >
                    凭证号
                  </th>
                  <th
                    className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground"
                    rowSpan={2}
                  >
                    摘要
                  </th>
                  {data.columns.map((col) => (
                    <th
                      key={col.account_code}
                      className="px-2 py-2.5 text-center text-xs font-medium text-muted-foreground"
                      colSpan={2}
                    >
                      {col.account_name}
                      <span className="block text-[10px] font-normal text-muted-foreground/60">
                        {col.account_code}
                      </span>
                    </th>
                  ))}
                  <th
                    className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground"
                    rowSpan={2}
                  >
                    借方合计
                  </th>
                  <th
                    className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground"
                    rowSpan={2}
                  >
                    贷方合计
                  </th>
                </tr>
                {/* Header Row 2: Debit/Credit sub-columns */}
                <tr className="border-b bg-gray-50">
                  {data.columns.map((col) => (
                    <>
                      <th
                        key={`${col.account_code}-d`}
                        className="px-2 py-1 text-right text-[10px] font-medium text-muted-foreground"
                      >
                        借方
                      </th>
                      <th
                        key={`${col.account_code}-c`}
                        className="px-2 py-1 text-right text-[10px] font-medium text-muted-foreground"
                      >
                        贷方
                      </th>
                    </>
                  ))}
                </tr>
              </thead>
              <tbody>
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
                    {data.columns.map((col) => {
                      const cv = row.column_values[col.account_code]
                      return (
                        <>
                          <td
                            key={`${idx}-${col.account_code}-d`}
                            className="px-2 py-2 text-right text-sm font-mono"
                          >
                            {cv ? fmt(parseFloat(cv.debit)) : ''}
                          </td>
                          <td
                            key={`${idx}-${col.account_code}-c`}
                            className="px-2 py-2 text-right text-sm font-mono"
                          >
                            {cv ? fmt(parseFloat(cv.credit)) : ''}
                          </td>
                        </>
                      )
                    })}
                    <td className="px-3 py-2 text-right text-sm font-mono">
                      {fmt(row.total_debit)}
                    </td>
                    <td className="px-3 py-2 text-right text-sm font-mono">
                      {fmt(row.total_credit)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 bg-gray-100 font-bold">
                  <td className="px-3 py-2 text-sm" colSpan={3}>
                    合计
                  </td>
                  {data.columns.map((col) => (
                    <>
                      <td
                        key={`foot-${col.account_code}-d`}
                        className="px-2 py-2 text-right text-sm font-mono"
                      >
                        {fmt(
                          data.rows.reduce(
                            (sum, r) =>
                              sum +
                              (r.column_values[col.account_code]
                                ? parseFloat(
                                    r.column_values[col.account_code].debit,
                                  )
                                : 0),
                            0,
                          ),
                        )}
                      </td>
                      <td
                        key={`foot-${col.account_code}-c`}
                        className="px-2 py-2 text-right text-sm font-mono"
                      >
                        {fmt(
                          data.rows.reduce(
                            (sum, r) =>
                              sum +
                              (r.column_values[col.account_code]
                                ? parseFloat(
                                    r.column_values[col.account_code].credit,
                                  )
                                : 0),
                            0,
                          ),
                        )}
                      </td>
                    </>
                  ))}
                  <td className="px-3 py-2 text-right text-sm font-mono">
                    {fmt(data.total_debit)}
                  </td>
                  <td className="px-3 py-2 text-right text-sm font-mono">
                    {fmt(data.total_credit)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* Account info card */}
      {data && data.account && (
        <div className="mt-4 flex items-center gap-4 text-sm text-muted-foreground">
          <span>
            查询科目：
            <span className="font-mono text-foreground font-medium ml-1">
              {data.account.code}
            </span>
            <span className="ml-1">{data.account.name}</span>
          </span>
          <span>
            对方科目列数：
            <span className="font-medium ml-1">{data.columns.length}</span>
          </span>
        </div>
      )}
    </div>
  )
}
