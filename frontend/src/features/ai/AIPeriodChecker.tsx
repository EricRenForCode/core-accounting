import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import api from '@/lib/api'
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  PlayCircle,
} from 'lucide-react'
import type { Period, PeriodCheckResponse } from '@/types/period'

const STATUS_META = {
  pass: { icon: CheckCircle, cls: 'text-green-600 bg-green-50', label: '通过' },
  warn: { icon: AlertTriangle, cls: 'text-amber-600 bg-amber-50', label: '警告' },
  fail: { icon: XCircle, cls: 'text-red-600 bg-red-50', label: '未通过' },
} as const

export default function AIPeriodCheckerPage() {
  const navigate = useNavigate()
  const [periodId, setPeriodId] = useState('')
  const [result, setResult] = useState<PeriodCheckResponse | null>(null)
  const [error, setError] = useState('')

  const { data: periodsData } = useQuery<{ periods: Period[] }>({
    queryKey: ['periods'],
    queryFn: async () => {
      const { data } = await api.get('/periods')
      return data
    },
  })
  const periods = periodsData?.periods || []

  useEffect(() => {
    if (!periodId && periods.length > 0) {
      setPeriodId(periods[0].id)
    }
  }, [periods, periodId])

  const mutation = useMutation({
    mutationFn: async (pid: string) => {
      const { data } = await api.post(`/ai/period/check?period_id=${pid}`)
      return data as PeriodCheckResponse
    },
    onSuccess: (data) => {
      setResult(data)
      setError('')
    },
    onError: (err: unknown) => {
      const data = (err as {
        response?: { data?: { detail?: string; error?: { message?: string } } }
      })?.response?.data
      setError(data?.detail || data?.error?.message || '检查失败')
    },
  })

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <CheckCircle className="h-5 w-5 text-primary" />
        期末检查
      </h2>
      <p className="text-sm text-muted-foreground">
        结账前自动运行完整性检查（未记账/未审核凭证、折旧、试算平衡、异常余额、银行未达账等），确认后再进入期末结转。
      </p>

      {/* Period selector + run */}
      <div className="flex items-center gap-3 rounded-lg border p-4">
        <label className="text-sm text-muted-foreground">会计期间</label>
        <select
          value={periodId}
          onChange={(e) => {
            setPeriodId(e.target.value)
            setResult(null)
          }}
          className="rounded-md border px-3 py-1.5 text-sm"
        >
          {periods.map((p) => (
            <option key={p.id} value={p.id}>
              {p.year}年{p.month}月（{p.status === 'open' ? '开放' : '已结账'}）
            </option>
          ))}
        </select>
        <button
          onClick={() => periodId && mutation.mutate(periodId)}
          disabled={!periodId || mutation.isPending}
          className="ml-auto flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <PlayCircle className="h-4 w-4" />
          )}
          运行检查
        </button>
      </div>

      {periods.length === 0 && (
        <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
          尚无会计期间，请先在「期间管理」创建。
        </div>
      )}

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-600">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          {/* Verdict banner */}
          <div
            className={`rounded-lg border px-4 py-3 text-sm font-medium ${
              result.can_close
                ? 'bg-green-50 border-green-200 text-green-700'
                : 'bg-amber-50 border-amber-200 text-amber-700'
            }`}
          >
            期末检查完成：
            {result.summary.pass} 通过 / {result.summary.warn} 警告 /{' '}
            {result.summary.fail} 失败。
            {result.can_close ? ' 可以进入期末结转。' : ' 请先处理警告或失败项。'}
          </div>

          {/* Check list */}
          <div className="rounded-lg border divide-y">
            {result.checks.map((check) => {
              const meta = STATUS_META[check.status] ?? STATUS_META.warn
              const Icon = meta.icon
              return (
                <div key={check.id} className="flex items-center gap-3 px-4 py-3">
                  <span className={`rounded-full p-1.5 ${meta.cls}`}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="flex-1">
                    <div className="text-sm font-medium">{check.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {check.detail}
                    </div>
                  </div>
                  <span className={`text-xs font-medium rounded px-2 py-0.5 ${meta.cls}`}>
                    {meta.label}
                  </span>
                </div>
              )
            })}
          </div>

          {result.can_close && (
            <div className="flex justify-end">
              <button
                onClick={() => navigate({ to: '/period/carry-forward' })}
                className="rounded-md border border-primary px-4 py-2 text-sm font-medium text-primary hover:bg-primary/5"
              >
                前往期末结转 →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
