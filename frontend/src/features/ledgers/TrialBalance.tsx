import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { ChevronDown, ChevronRight, Download } from 'lucide-react'

interface TrialBalanceRow {
  account_id: string
  code: string
  name: string
  level: number
  opening_debit: number
  opening_credit: number
  current_debit: number
  current_credit: number
  closing_debit: number
  closing_credit: number
  opening_balance: number
  closing_balance: number
  children: TrialBalanceRow[]
}

interface TrialBalanceData {
  period: { year: number; month: number }
  rows: TrialBalanceRow[]
  summary: {
    total_opening_debit: number
    total_opening_credit: number
    total_current_debit: number
    total_current_credit: number
    total_closing_debit: number
    total_closing_credit: number
  }
}

function fmt(n: number | string): string {
  const val = typeof n === 'string' ? parseFloat(n) : n
  if (val === 0) return ''
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function RowItem({
  row,
  expanded,
  onToggle,
}: {
  row: TrialBalanceRow
  expanded: Set<string>
  onToggle: (id: string) => void
}) {
  const hasChildren = row.children && row.children.length > 0
  const isExpanded = expanded.has(row.account_id)
  const indent = row.level - 1

  return (
    <>
      <tr
        className={`border-b hover:bg-gray-50/50 transition-colors cursor-pointer ${
          row.level === 1 ? 'font-semibold bg-gray-50/30' : ''
        }`}
        onClick={() => hasChildren && onToggle(row.account_id)}
      >
        <td className="px-3 py-2 text-sm">
          <span style={{ paddingLeft: `${indent * 20}px` }} className="inline-flex items-center gap-1">
            {hasChildren && (
              <span className="text-muted-foreground">
                {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </span>
            )}
            <span className="font-mono text-xs text-muted-foreground">{row.code}</span>
          </span>
        </td>
        <td className="px-3 py-2 text-sm">{row.name}</td>
        <td className="px-3 py-2 text-right text-sm font-mono">{fmt(row.opening_debit)}</td>
        <td className="px-3 py-2 text-right text-sm font-mono">{fmt(row.opening_credit)}</td>
        <td className="px-3 py-2 text-right text-sm font-mono">{fmt(row.current_debit)}</td>
        <td className="px-3 py-2 text-right text-sm font-mono">{fmt(row.current_credit)}</td>
        <td className="px-3 py-2 text-right text-sm font-mono">{fmt(row.closing_debit)}</td>
        <td className="px-3 py-2 text-right text-sm font-mono">{fmt(row.closing_credit)}</td>
      </tr>
      {isExpanded &&
        row.children.map((child) => (
          <RowItem
            key={child.account_id}
            row={child}
            expanded={expanded}
            onToggle={onToggle}
          />
        ))}
    </>
  )
}

export default function TrialBalance() {
  const [level, setLevel] = useState<number | undefined>(undefined)
  const [includeZero, setIncludeZero] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  // Use period_id from store or default
  const periodId = 'current' // placeholder — would come from useCurrentPeriod()

  const { data, isLoading, isError } = useQuery<TrialBalanceData>({
    queryKey: ['trial-balance', periodId, level, includeZero],
    queryFn: async () => {
      const params: Record<string, string | number | boolean> = {
        period_id: periodId,
        include_zero: includeZero,
      }
      if (level) params.level = level
      const { data } = await api.get<TrialBalanceData>('/reports/trial-balance', { params })
      return data
    },
    enabled: periodId !== 'current',
    staleTime: 300_000, // 5 min cache
  })

  function toggleAll() {
    if (!data) return
    if (expanded.size > 0) {
      setExpanded(new Set())
    } else {
      const allIds = new Set<string>()
      function collect(rows: TrialBalanceRow[]) {
        for (const r of rows) {
          if (r.children && r.children.length > 0) {
            allIds.add(r.account_id)
            collect(r.children)
          }
        }
      }
      collect(data.rows)
      setExpanded(allIds)
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">科目余额表</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.period
              ? `${data.period.year}年${data.period.month}月`
              : '加载中...'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Level filter */}
          <select
            value={level ?? ''}
            onChange={(e) => {
              const v = e.target.value
              setLevel(v ? parseInt(v) : undefined)
            }}
            className="rounded-md border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          >
            <option value="">全部层级</option>
            <option value="1">一级科目</option>
            <option value="2">二级科目</option>
            <option value="3">三级科目</option>
            <option value="4">四级科目</option>
          </select>

          {/* Include zero toggle */}
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={includeZero}
              onChange={(e) => setIncludeZero(e.target.checked)}
              className="rounded"
            />
            含零余额
          </label>

          {/* Expand/Collapse */}
          <button
            onClick={toggleAll}
            className="text-sm text-accent hover:underline"
          >
            {expanded.size > 0 ? '全部收起' : '全部展开'}
          </button>

          {/* Export */}
          <button className="flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm hover:bg-gray-50 transition-colors">
            <Download size={14} />
            导出
          </button>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          <p>加载中...</p>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-lg border bg-red-50 p-8 text-center">
          <p className="text-red-600 font-medium">加载科目余额表失败</p>
          <p className="text-sm text-red-500 mt-1">
            请确认已选择有效的会计期间
          </p>
        </div>
      )}

      {/* Empty */}
      {data && data.rows.length === 0 && (
        <div className="rounded-lg border bg-card p-12 text-center">
          <p className="text-lg text-muted-foreground">暂无余额数据</p>
          <p className="text-sm text-muted-foreground mt-1">
            该期间可能尚无已记账凭证
          </p>
        </div>
      )}

      {/* Table */}
      {data && data.rows.length > 0 && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="w-32 px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">
                    科目编码
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">
                    科目名称
                  </th>
                  <th className="w-36 px-3 py-2.5 text-right text-xs font-medium text-muted-foreground" colSpan={2}>
                    期初余额
                  </th>
                  <th className="w-36 px-3 py-2.5 text-right text-xs font-medium text-muted-foreground" colSpan={2}>
                    本期发生额
                  </th>
                  <th className="w-36 px-3 py-2.5 text-right text-xs font-medium text-muted-foreground" colSpan={2}>
                    期末余额
                  </th>
                </tr>
                <tr className="border-b bg-gray-50">
                  <th />
                  <th />
                  <th className="w-18 px-3 py-1 text-right text-[10px] font-medium text-muted-foreground">借方</th>
                  <th className="w-18 px-3 py-1 text-right text-[10px] font-medium text-muted-foreground">贷方</th>
                  <th className="w-18 px-3 py-1 text-right text-[10px] font-medium text-muted-foreground">借方</th>
                  <th className="w-18 px-3 py-1 text-right text-[10px] font-medium text-muted-foreground">贷方</th>
                  <th className="w-18 px-3 py-1 text-right text-[10px] font-medium text-muted-foreground">借方</th>
                  <th className="w-18 px-3 py-1 text-right text-[10px] font-medium text-muted-foreground">贷方</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <RowItem
                    key={row.account_id}
                    row={row}
                    expanded={expanded}
                    onToggle={(id) =>
                      setExpanded((prev) => {
                        const next = new Set(prev)
                        if (next.has(id)) next.delete(id)
                        else next.add(id)
                        return next
                      })
                    }
                  />
                ))}
              </tbody>
              {/* Summary Row */}
              <tfoot>
                <tr className="border-t-2 bg-gray-100 font-bold">
                  <td className="px-3 py-2 text-sm" colSpan={2}>
                    合计
                  </td>
                  <td className="px-3 py-2 text-right text-sm font-mono">
                    {fmt(data.summary.total_opening_debit)}
                  </td>
                  <td className="px-3 py-2 text-right text-sm font-mono">
                    {fmt(data.summary.total_opening_credit)}
                  </td>
                  <td className="px-3 py-2 text-right text-sm font-mono">
                    {fmt(data.summary.total_current_debit)}
                  </td>
                  <td className="px-3 py-2 text-right text-sm font-mono">
                    {fmt(data.summary.total_current_credit)}
                  </td>
                  <td className="px-3 py-2 text-right text-sm font-mono">
                    {fmt(data.summary.total_closing_debit)}
                  </td>
                  <td className="px-3 py-2 text-right text-sm font-mono">
                    {fmt(data.summary.total_closing_credit)}
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
