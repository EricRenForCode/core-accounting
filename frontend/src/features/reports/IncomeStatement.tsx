import { useQuery } from '@tanstack/react-query'
import { useSearch } from '@tanstack/react-router'
import api from '@/lib/api'
import { useCurrentPeriod } from '@/hooks/useCurrentPeriod'
import { Skeleton } from '@/components/Skeleton'
import { ErrorCard } from '@/components/ErrorCard'
import type {
  IncomeStatementResponse,
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

export default function IncomeStatementPage() {
  const search = useSearch({ from: '/reports/income' }) as {
    period_id?: string
  }
  const { currentPeriod, isLoading: periodLoading } = useCurrentPeriod()

  const periodId = search.period_id || currentPeriod?.id

  const {
    data,
    isLoading,
    error,
  } = useQuery<IncomeStatementResponse>({
    queryKey: ['income-statement', periodId],
    queryFn: async () => {
      const { data } = await api.get('/statements/income', {
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
          title="加载利润表失败"
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
      {/* Header */}
      <div className="text-center mb-6">
        <h2 className="text-xl font-bold">利润表</h2>
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
              <th className="py-2 pl-4 text-left w-1/2">项目</th>
              <th className="py-2 pr-3 text-right w-1/4">本期金额</th>
              <th className="py-2 pr-2 text-right w-1/4">本年累计</th>
            </tr>
          </thead>
          <tbody>
            {data.sections.map(
              (section: BalanceSheetSection, si: number) => (
                <>
                  {/* Section label */}
                  <tr key={`h-${si}`} className="bg-muted/20">
                    <td
                      colSpan={3}
                      className="py-1.5 pl-4 font-semibold text-xs text-muted-foreground"
                    >
                      {section.label}
                    </td>
                  </tr>
                  {/* Items */}
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
                            {neg && (
                              <span className="text-xs text-muted-foreground ml-1">
                                (减)
                              </span>
                            )}
                          </td>
                          <td className="py-1.5 pr-3 text-right tabular-nums">
                            {neg
                              ? `-${fmt(item.closing)}`
                              : fmt(item.closing)}
                          </td>
                          <td className="py-1.5 pr-2 text-right tabular-nums text-muted-foreground">
                            {neg
                              ? `-${fmt(item.opening)}`
                              : fmt(item.opening)}
                          </td>
                        </tr>
                      )
                    },
                  )}
                  {/* Subtotal */}
                  <tr className="border-t font-medium">
                    <td className="py-1.5 pl-8">小计</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">
                      {fmt(section.subtotal.closing)}
                    </td>
                    <td className="py-1.5 pr-2 text-right tabular-nums text-muted-foreground">
                      {fmt(section.subtotal.opening)}
                    </td>
                  </tr>
                </>
              ),
            )}

            {/* Totals */}
            {data.totals && (
              <>
                {/* 营业利润 */}
                {(data.totals as Record<string, { closing: string; opening: string }>)
                  .operating_profit && (
                  <tr className="border-t-2 font-semibold bg-muted/10">
                    <td className="py-2 pl-4">二、营业利润</td>
                    <td className="py-2 pr-3 text-right tabular-nums">
                      {fmt(
                        (data.totals as Record<
                          string,
                          { closing: string; opening: string }
                        >).operating_profit.closing,
                      )}
                    </td>
                    <td className="py-2 pr-2 text-right tabular-nums text-muted-foreground">
                      {fmt(
                        (data.totals as Record<
                          string,
                          { closing: string; opening: string }
                        >).operating_profit.opening,
                      )}
                    </td>
                  </tr>
                )}

                {/* 净利润 */}
                {(data.totals as Record<string, { closing: string; opening: string }>)
                  .net_profit && (
                  <tr className="border-t-2 border-double font-bold">
                    <td className="py-2 pl-4">四、净利润</td>
                    <td className="py-2 pr-3 text-right tabular-nums">
                      {fmt(
                        (data.totals as Record<
                          string,
                          { closing: string; opening: string }
                        >).net_profit.closing,
                      )}
                    </td>
                    <td className="py-2 pr-2 text-right tabular-nums text-muted-foreground">
                      {fmt(
                        (data.totals as Record<
                          string,
                          { closing: string; opening: string }
                        >).net_profit.opening,
                      )}
                    </td>
                  </tr>
                )}
              </>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
