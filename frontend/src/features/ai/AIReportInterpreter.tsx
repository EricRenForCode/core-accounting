import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'
import { useCurrentPeriod } from '@/hooks/useCurrentPeriod'
import { BarChart3, Send, Loader2, TrendingUp, AlertTriangle } from 'lucide-react'

interface ReportInterpretation {
  period_id: string
  report_type: string
  interpretation: string
  highlights: string[]
  warnings: string[]
}

const REPORT_TYPES = [
  { value: 'balance_sheet', label: '资产负债表' },
  { value: 'income', label: '利润表' },
  { value: 'cash_flow', label: '现金流量表' },
]

export default function AIReportInterpreterPage() {
  const { currentPeriod } = useCurrentPeriod()
  const [reportType, setReportType] = useState('balance_sheet')
  const [result, setResult] = useState<ReportInterpretation | null>(null)
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post('/ai/reports/interpret', {
        period_id: currentPeriod?.id,
        report_type: reportType,
      })
      return data as ReportInterpretation
    },
    onSuccess: (data) => {
      setResult(data)
      setError('')
    },
    onError: (err: unknown) => {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || 'AI 分析失败',
      )
    },
  })

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <BarChart3 className="h-5 w-5 text-primary" />
        报表智能解读
      </h2>

      <div className="rounded-lg border p-4 space-y-3">
        <label className="block text-sm font-medium">选择报表类型</label>
        <div className="flex gap-2">
          {REPORT_TYPES.map((rt) => (
            <button
              key={rt.value}
              onClick={() => setReportType(rt.value)}
              className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                reportType === rt.value
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted hover:bg-muted/70'
              }`}
            >
              {rt.label}
            </button>
          ))}
        </div>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !currentPeriod}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {mutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              分析中...
            </>
          ) : (
            <>
              <Send className="h-4 w-4" />
              开始分析
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-600">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="rounded-lg border p-4 bg-blue-50/50">
            <h3 className="font-semibold text-sm mb-2">📊 总体解读</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {result.interpretation}
            </p>
          </div>

          {result.highlights.length > 0 && (
            <div className="rounded-lg border p-4 bg-green-50/50">
              <h3 className="font-semibold text-sm mb-2 flex items-center gap-1">
                <TrendingUp className="h-4 w-4 text-green-600" />
                关键亮点
              </h3>
              <ul className="space-y-1">
                {result.highlights.map((h, i) => (
                  <li
                    key={i}
                    className="text-sm text-muted-foreground flex gap-2"
                  >
                    <span className="text-green-600">✓</span> {h}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.warnings.length > 0 && (
            <div className="rounded-lg border p-4 bg-amber-50/50">
              <h3 className="font-semibold text-sm mb-2 flex items-center gap-1">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                风险提示
              </h3>
              <ul className="space-y-1">
                {result.warnings.map((w, i) => (
                  <li
                    key={i}
                    className="text-sm text-muted-foreground flex gap-2"
                  >
                    <span className="text-amber-600">⚠</span> {w}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
