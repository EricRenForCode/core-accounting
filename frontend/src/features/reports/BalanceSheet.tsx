import { useQuery } from '@tanstack/react-query'
import { useSearch } from '@tanstack/react-router'
import api from '@/lib/api'
import { useCurrentPeriod } from '@/hooks/useCurrentPeriod'
import { Skeleton } from '@/components/Skeleton'
import { ErrorCard } from '@/components/ErrorCard'
import type {
  BalanceSheetResponse,
  BalanceSheetSection,
  BalanceSheetItem,
} from '@/types/report'

function fmt(n: number | string): string {
  const val = typeof n === 'string' ? parseFloat(n) : n
  if (isNaN(val)) return ''
  return Math.abs(val).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function isNegative(n: number | string): boolean {
  const val = typeof n === 'string' ? parseFloat(n) : n
  return val < 0
}

function SectionBlock({
  section,
  side,
}: {
  section: BalanceSheetSection
  side: 'assets' | 'liabilities_equity'
}) {
  return (
    <div className="mb-2">
      <div className="bg-muted/50 px-3 py-1.5 rounded font-semibold text-sm text-muted-foreground">
        {section.label}
      </div>
      <table className="w-full text-sm">
        <tbody>
          {section.items.map((item: BalanceSheetItem, idx: number) => {
            const neg = isNegative(item.closing)
            return (
              <tr key={idx} className="border-b border-dashed last:border-0">
                <td className="py-1.5 pl-4 text-left">
                  {item.name}
                  {neg && (
                    <span className="text-xs text-muted-foreground ml-1">
                      (减)
                    </span>
                  )}
                </td>
                <td className="py-1.5 pr-3 text-right tabular-nums w-28">
                  {neg ? `-${fmt(item.closing)}` : fmt(item.closing) || '—'}
                </td>
                <td className="py-1.5 pr-2 text-right tabular-nums w-28 text-muted-foreground">
                  {neg
                    ? `-${fmt(item.opening)}`
                    : fmt(item.opening) || '—'}
                </td>
              </tr>
            )
          })}
          <tr className="border-t font-medium bg-muted/20">
            <td className="py-1.5 pl-4 text-left">{section.label} 合计</td>
            <td className="py-1.5 pr-3 text-right tabular-nums w-28">
              {fmt(section.subtotal.closing) || '—'}
            </td>
            <td className="py-1.5 pr-2 text-right tabular-nums w-28 text-muted-foreground">
              {fmt(section.subtotal.opening) || '—'}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

export default function BalanceSheetPage() {
  const search = useSearch({ from: '/reports/balance-sheet' }) as {
    period_id?: string
  }
  const { currentPeriod, isLoading: periodLoading } = useCurrentPeriod()

  const periodId = search.period_id || currentPeriod?.id

  const {
    data,
    isLoading,
    error,
  } = useQuery<BalanceSheetResponse>({
    queryKey: ['balance-sheet', periodId],
    queryFn: async () => {
      const { data } = await api.get('/statements/balance-sheet', {
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
          title="加载资产负债表失败"
          message={(error as Error)?.message || '请检查会计期间设置'}
        />
      </div>
    )
  }

  if (isLoading || !data) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 gap-6">
          <Skeleton className="h-80 w-full" />
          <Skeleton className="h-80 w-full" />
        </div>
      </div>
    )
  }

  // Split sections: assets go left, liabilities+equity go right
  const assetSections: BalanceSheetSection[] = []
  const liabilityEquitySections: BalanceSheetSection[] = []

  for (const section of data.sections) {
    // Assets sections appear first in the template definition
    if (
      data.sections.indexOf(section) <
      data.sections.findIndex(
        (s) =>
          s.label.includes('负债') ||
          s.label.includes('权益') ||
          s.label.includes('所有者'),
      )
    ) {
      assetSections.push(section)
    } else {
      liabilityEquitySections.push(section)
    }
  }

  // Fallback: if findIndex fails, use label content to split
  if (assetSections.length === 0 || liabilityEquitySections.length === 0) {
    assetSections.length = 0
    liabilityEquitySections.length = 0
    for (const section of data.sections) {
      if (
        section.label.includes('负债') ||
        section.label.includes('权益') ||
        section.label.includes('所有者')
      ) {
        liabilityEquitySections.push(section)
      } else {
        assetSections.push(section)
      }
    }
  }

  const assetsClosing = parseFloat(data.totals.assets.closing)
  const liabilitiesEquityClosing = parseFloat(
    data.totals.liabilities_equity.closing,
  )
  const isBalanced = Math.abs(assetsClosing - liabilitiesEquityClosing) < 0.01

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="text-center mb-6">
        <h2 className="text-xl font-bold">资产负债表</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {data.period.year}年{data.period.month}月 | 模板：{data.template.name}
        </p>
        <div className="text-xs text-muted-foreground mt-0.5">单位：元</div>
      </div>

      {/* Balance check */}
      <div
        className={`mb-4 rounded-md px-3 py-2 text-sm text-center ${
          isBalanced
            ? 'bg-green-50 border border-green-200 text-green-700'
            : 'bg-red-50 border border-red-200 text-red-700'
        }`}
      >
        {isBalanced ? (
          <span>✓ 资产负债表平衡 — 资产总计 = 负债及所有者权益总计</span>
        ) : (
          <span>
            ✗ 资产负债表不平衡 — 差额:{' '}
            {fmt(assetsClosing - liabilitiesEquityClosing)} 元
          </span>
        )}
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-2 gap-8">
        {/* Left: Assets */}
        <div>
          <h3 className="text-base font-bold text-center mb-3 border-b pb-1">
            资产
          </h3>
          <table className="w-full text-sm mb-1">
            <thead>
              <tr className="border-b text-muted-foreground text-xs">
                <th className="py-1 text-left pl-4">项目</th>
                <th className="py-1 text-right pr-3 w-28">期末余额</th>
                <th className="py-1 text-right pr-2 w-28">期初余额</th>
              </tr>
            </thead>
          </table>
          {assetSections.map((section, i) => (
            <SectionBlock key={i} section={section} side="assets" />
          ))}
          {/* Assets Total */}
          <div className="border-t-2 border-double pt-1 mt-2 font-bold">
            <table className="w-full text-sm">
              <tbody>
                <tr>
                  <td className="py-1.5 pl-4 text-left">资产总计</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums w-28">
                    {fmt(data.totals.assets.closing) || '—'}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums w-28 text-muted-foreground">
                    {fmt(data.totals.assets.opening) || '—'}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: Liabilities + Equity */}
        <div>
          <h3 className="text-base font-bold text-center mb-3 border-b pb-1">
            负债及所有者权益
          </h3>
          <table className="w-full text-sm mb-1">
            <thead>
              <tr className="border-b text-muted-foreground text-xs">
                <th className="py-1 text-left pl-4">项目</th>
                <th className="py-1 text-right pr-3 w-28">期末余额</th>
                <th className="py-1 text-right pr-2 w-28">期初余额</th>
              </tr>
            </thead>
          </table>
          {liabilityEquitySections.map((section, i) => (
            <SectionBlock key={i} section={section} side="liabilities_equity" />
          ))}
          {/* Liabilities + Equity Total */}
          <div className="border-t-2 border-double pt-1 mt-2 font-bold">
            <table className="w-full text-sm">
              <tbody>
                <tr>
                  <td className="py-1.5 pl-4 text-left">
                    负债及所有者权益总计
                  </td>
                  <td className="py-1.5 pr-3 text-right tabular-nums w-28">
                    {fmt(data.totals.liabilities_equity.closing) || '—'}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums w-28 text-muted-foreground">
                    {fmt(data.totals.liabilities_equity.opening) || '—'}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
