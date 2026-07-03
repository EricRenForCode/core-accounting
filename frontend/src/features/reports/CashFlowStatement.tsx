import { useQuery } from '@tanstack/react-query'
import { useSearch } from '@tanstack/react-router'
import api from '@/lib/api'
import { useCurrentPeriod } from '@/hooks/useCurrentPeriod'
import { Skeleton } from '@/components/Skeleton'
import { ErrorCard } from '@/components/ErrorCard'
import { ExportButton } from '@/components/ExportButton'
import type {
  CashFlowStatementResponse,
  BalanceSheetSection,
  BalanceSheetItem,
} from '@/types/report'

function fmt(n: number | string): string {
  const val = typeof n === 'string' ? parseFloat(n) : n
  if (isNaN(val)) return '—'
  return Math.abs(val).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function isNegative(n: number | string): boolean {
  const val = typeof n === 'string' ? parseFloat(n) : n
  return val < 0
}

export default function CashFlowStatementPage() {
  const search = useSearch({ from: '/authenticated/reports/cash-flow' }) as {
    period_id?: string
  }
  const { currentPeriod, isLoading: periodLoading } = useCurrentPeriod()

  const periodId = search.period_id || currentPeriod?.id

  const {
    data,
    isLoading,
    error,
  } = useQuery<CashFlowStatementResponse>({
    queryKey: ['cash-flow', periodId],
    queryFn: async () => {
      const { data } = await api.get('/statements/cash-flow', {
        params: { period_id: periodId },
      })
      return data
    },
    enabled: !!periodId,
  })

  if (periodLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <ErrorCard
          title="加载现金流量表失败"
          message={(error as Error)?.message || '请检查会计期间设置'}
        />
      </div>
    )
  }

  if (isLoading || !data) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-80 w-full" />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Toolbar */}
      <div className="flex justify-end mb-2">
        <ExportButton type="cash_flow" periodId={periodId} />
      </div>

      {/* Header */}
      <div className="text-center mb-6">
        <h2 className="text-xl font-bold">现金流量表</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {data.period.year}年{data.period.month}月 | 模板：{data.template.name}
        </p>
        <div className="text-xs text-muted-foreground mt-0.5">单位：元</div>
      </div>

      {/* Table */}
      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/50 border-b">
              <th className="py-2 pl-4 text-left">项目</th>
              <th className="py-2 pr-3 text-right w-32">本期金额</th>
            </tr>
          </thead>
          <tbody>
            {data.sections.map(
              (section: BalanceSheetSection, si: number) => (
                <>
                  <tr key={`h-${si}`} className="bg-muted/20">
                    <td
                      colSpan={2}
                      className="py-1.5 pl-4 font-semibold text-xs text-muted-foreground"
                    >
                      {section.label}
                    </td>
                  </tr>
                  {section.items.map(
                    (item: BalanceSheetItem, ii: number) => {
                      const neg = isNegative(item.closing)
                      return (
                        <tr
                          key={`${si}-${ii}`}
                          className="border-b border-dashed last:border-b-0 hover:bg-gray-50/30"
                        >
                          <td className="py-1.5 pl-8">
                            {item.name}
                          </td>
                          <td
                            className={`py-1.5 pr-3 text-right tabular-nums ${
                              neg ? 'text-red-600' : ''
                            }`}
                          >
                            {neg
                              ? `-${fmt(item.closing)}`
                              : fmt(item.closing)}
                          </td>
                        </tr>
                      )
                    },
                  )}
                  <tr className="border-t font-medium">
                    <td className="py-1.5 pl-8">
                      {section.label.replace('产生的现金流量', '现金流量净额')}
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">
                      {fmt(section.subtotal.closing)}
                    </td>
                  </tr>
                </>
              ),
            )}

            {/* Net increase */}
            {data.totals?.net_increase && (
              <tr className="border-t-2 border-double font-bold">
                <td className="py-2 pl-4">现金及现金等价物净增加额</td>
                <td className="py-2 pr-3 text-right tabular-nums">
                  {fmt(data.totals.net_increase.closing)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
