import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { useCurrentPeriod } from '@/hooks/useCurrentPeriod'
import { useUserStore } from '@/stores/userStore'
import { Skeleton } from '@/components/Skeleton'
import { ErrorCard } from '@/components/ErrorCard'
import {
  Lock,
  Unlock,
  AlertTriangle,
  CheckCircle,
  XCircle,
} from 'lucide-react'

interface Period {
  id: string
  year: number
  month: number
  status: 'open' | 'closed'
  closed_at?: string
}

interface CheckItem {
  id: number
  name: string
  status: 'pass' | 'warn' | 'fail'
  detail: string
}

interface CheckResponse {
  period_id: string
  checks: CheckItem[]
  summary: { pass: number; warn: number; fail: number }
  can_close: boolean
}

interface TrialBalance {
  is_balanced: boolean
  total_debit: number
  total_credit: number
  difference: number
}

const STATUS_ICON: Record<string, typeof CheckCircle> = {
  pass: CheckCircle,
  warn: AlertTriangle,
  fail: XCircle,
}

const STATUS_COLOR: Record<string, string> = {
  pass: 'text-green-600',
  warn: 'text-amber-600',
  fail: 'text-red-600',
}

export default function PeriodClosePage() {
  const queryClient = useQueryClient()
  const { currentPeriod, isLoading: periodLoading } = useCurrentPeriod()
  const canClose = useUserStore((s) => s.can('period:close'))
  const canReopen = useUserStore((s) => s.can('period:reopen'))
  const [error, setError] = useState('')

  const periodId = currentPeriod?.id

  // Pre-close check
  const { data: checkData, isLoading: checkLoading } = useQuery<CheckResponse>(
    {
      queryKey: ['period-check', periodId],
      queryFn: async () => {
        const { data } = await api.get('/carry-forward/check', {
          params: { period_id: periodId },
        })
        return data
      },
      enabled: !!periodId,
    },
  )

  // Trial balance
  const { data: trialBalance } = useQuery<TrialBalance>({
    queryKey: ['period-trial-balance', periodId],
    queryFn: async () => {
      const { data } = await api.get(`/periods/${periodId}/trial-balance`)
      return data
    },
    enabled: !!periodId,
  })

  const closeMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.post(`/periods/${id}/close`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['current-period'] })
      queryClient.invalidateQueries({ queryKey: ['period-check'] })
      setError('')
    },
    onError: (err: unknown) => {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || '结账失败',
      )
    },
  })

  const reopenMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.post(`/periods/${id}/reopen`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['current-period'] })
      queryClient.invalidateQueries({ queryKey: ['period-check'] })
      setError('')
    },
    onError: (err: unknown) => {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || '反结账失败',
      )
    },
  })

  if (periodLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!currentPeriod) {
    return (
      <div className="p-6">
        <ErrorCard title="未找到会计期间" message="请先创建会计期间" />
      </div>
    )
  }

  const isClosed = currentPeriod.status === 'closed'

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <h2 className="text-xl font-bold">结账管理</h2>

      {/* Period info */}
      <div className="rounded-lg border p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">当前会计期间</p>
            <p className="text-lg font-bold">
              {currentPeriod.year}年{currentPeriod.month}月
            </p>
          </div>
          <div
            className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ${
              isClosed
                ? 'bg-gray-100 text-gray-600'
                : 'bg-green-100 text-green-700'
            }`}
          >
            {isClosed ? (
              <>
                <Lock className="h-4 w-4" />
                已结账
              </>
            ) : (
              <>
                <CheckCircle className="h-4 w-4" />
                开放中
              </>
            )}
          </div>
        </div>
        {currentPeriod.closed_at && (
          <p className="text-xs text-muted-foreground mt-2">
            结账时间: {new Date(currentPeriod.closed_at).toLocaleString('zh-CN')}
          </p>
        )}
      </div>

      {/* Trial balance */}
      {trialBalance && (
        <div
          className={`rounded-lg border p-4 ${
            trialBalance.is_balanced
              ? 'bg-green-50 border-green-200'
              : 'bg-red-50 border-red-200'
          }`}
        >
          <h3 className="font-semibold text-sm mb-2">试算平衡</h3>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">借方合计</span>
              <p className="font-mono font-medium">
                {(trialBalance.total_debit as number).toLocaleString('zh-CN', {
                  minimumFractionDigits: 2,
                })}
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">贷方合计</span>
              <p className="font-mono font-medium">
                {(trialBalance.total_credit as number).toLocaleString('zh-CN', {
                  minimumFractionDigits: 2,
                })}
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">差额</span>
              <p
                className={`font-mono font-medium ${
                  trialBalance.is_balanced
                    ? 'text-green-600'
                    : 'text-red-600'
                }`}
              >
                {(trialBalance.difference as number).toLocaleString('zh-CN', {
                  minimumFractionDigits: 2,
                })}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Check results */}
      {checkLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : checkData ? (
        <div className="rounded-lg border p-4">
          <h3 className="font-semibold text-sm mb-3">
            期末检查 (
            {checkData.summary.pass}通过 / {checkData.summary.warn}警告 /{' '}
            {checkData.summary.fail}失败)
          </h3>
          <div className="space-y-2">
            {checkData.checks.map((check) => {
              const Icon = STATUS_ICON[check.status]
              return (
                <div
                  key={check.id}
                  className="flex items-center gap-2 text-sm"
                >
                  <Icon className={`h-4 w-4 ${STATUS_COLOR[check.status]}`} />
                  <span className="font-medium w-24">{check.name}</span>
                  <span className="text-muted-foreground">{check.detail}</span>
                </div>
              )
            })}
          </div>
        </div>
      ) : null}

      {/* Actions */}
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-600">
          {error}
        </div>
      )}

      <div className="flex gap-3">
        {!isClosed && canClose && (
          <button
            onClick={() => closeMutation.mutate(currentPeriod.id)}
            disabled={closeMutation.isPending || (checkData ? !checkData.can_close : false)}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Lock className="h-4 w-4" />
            {closeMutation.isPending ? '结账中...' : '执行结账'}
          </button>
        )}
        {isClosed && canReopen && (
          <button
            onClick={() => reopenMutation.mutate(currentPeriod.id)}
            disabled={reopenMutation.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Unlock className="h-4 w-4" />
            {reopenMutation.isPending ? '反结账中...' : '反结账'}
          </button>
        )}
      </div>

      {!isClosed && checkData && !checkData.can_close && (
        <p className="text-sm text-amber-600">
          ⚠️ 存在未通过的检查项，请先处理后再执行结账
        </p>
      )}
    </div>
  )
}
