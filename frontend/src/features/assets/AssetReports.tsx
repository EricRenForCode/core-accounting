import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { Download } from 'lucide-react'

interface AssetReport {
  period: { year: number; month: number }
  total_assets: number
  total_original_value: number
  total_accumulated_depreciation: number
  total_net_value: number
  by_category: Array<{ category: string; count: number; original: string; depreciation: string; net: string }>
  by_status: Array<{ status: string; count: number; net_value: string }>
}

const STATUS_LABELS: Record<string, string> = {
  in_use: '使用中', disposed: '已处置', cleared: '已清理',
}

function fmt(n: number | string): string {
  const val = typeof n === 'string' ? parseFloat(n) : n
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function AssetReports() {
  const [periodId, setPeriodId] = useState('')

  const { data, isLoading, isError } = useQuery<AssetReport>({
    queryKey: ['asset-reports', periodId],
    queryFn: async () => {
      const { data } = await api.get<AssetReport>('/fixed-assets/reports', { params: { period_id: periodId } })
      return data
    },
    enabled: !!periodId,
  })

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">固定资产报表</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.period && `${data.period.year}年${data.period.month}月`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input type="text" value={periodId} onChange={(e) => setPeriodId(e.target.value)} className="rounded-md border px-3 py-1.5 text-sm font-mono w-48 focus:outline-none focus:ring-2 focus:ring-accent" placeholder="期间ID" />
          <button className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-gray-50">
            <Download size={14} />导出
          </button>
        </div>
      </div>

      {isLoading && <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">加载中...</div>}
      {isError && <div className="rounded-lg border bg-red-50 p-8 text-center"><p className="text-red-600 font-medium">加载资产报表失败</p></div>}
      {!periodId && <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground"><p className="text-lg">请输入期间ID查询资产报表</p></div>}

      {data && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            {[
              { label: '资产总数', value: data.total_assets },
              { label: '原值合计', value: fmt(data.total_original_value) },
              { label: '累计折旧', value: fmt(data.total_accumulated_depreciation) },
              { label: '净值合计', value: fmt(data.total_net_value) },
            ].map((card) => (
              <div key={card.label} className="rounded-lg border bg-card p-4">
                <p className="text-sm text-muted-foreground">{card.label}</p>
                <p className="text-2xl font-bold font-mono mt-1">{typeof card.value === 'number' ? card.value : card.value}</p>
              </div>
            ))}
          </div>

          {/* By Category */}
          {data.by_category.length > 0 && (
            <div className="rounded-lg border bg-card overflow-hidden mb-6">
              <div className="px-4 py-3 bg-gray-50 border-b font-medium text-sm">按类别汇总</div>
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">类别</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">数量</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">原值</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">折旧</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">净值</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_category.map((c, i) => (
                    <tr key={i} className="border-b hover:bg-gray-50/50">
                      <td className="px-3 py-2 text-sm font-medium">{c.category}</td>
                      <td className="px-3 py-2 text-right text-sm">{c.count}</td>
                      <td className="px-3 py-2 text-right text-sm font-mono">{fmt(c.original)}</td>
                      <td className="px-3 py-2 text-right text-sm font-mono">{fmt(c.depreciation)}</td>
                      <td className="px-3 py-2 text-right text-sm font-mono font-medium">{fmt(c.net)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 bg-gray-100 font-bold">
                    <td className="px-3 py-2 text-sm">合计</td>
                    <td className="px-3 py-2 text-right text-sm">{data.total_assets}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono">{fmt(data.total_original_value)}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono">{fmt(data.total_accumulated_depreciation)}</td>
                    <td className="px-3 py-2 text-right text-sm font-mono">{fmt(data.total_net_value)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}

          {/* By Status */}
          {data.by_status.length > 0 && (
            <div className="rounded-lg border bg-card overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 border-b font-medium text-sm">按状态汇总</div>
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">状态</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">数量</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">净值</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_status.map((s, i) => (
                    <tr key={i} className="border-b hover:bg-gray-50/50">
                      <td className="px-3 py-2 text-sm">{STATUS_LABELS[s.status] || s.status}</td>
                      <td className="px-3 py-2 text-right text-sm">{s.count}</td>
                      <td className="px-3 py-2 text-right text-sm font-mono">{fmt(s.net_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
