import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { usePermission } from '@/hooks/usePermission'
import { useCurrentPeriod } from '@/hooks/useCurrentPeriod'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { StatusBadge } from '@/components/StatusBadge'
import { EmptyState } from '@/components/EmptyState'
import { ErrorCard } from '@/components/ErrorCard'
import { Skeleton } from '@/components/Skeleton'
import { cn, formatDate, formatAmount } from '@/lib/utils'
import {
  Plus,
  ChevronDown,
  ChevronRight,
  Lock,
  Unlock,
  Calculator,
  X,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react'
import type { Period } from '@/types/period'
import { PeriodStatus } from '@/lib/constants'

// ─── Local Types ─────────────────────────────────────

interface TrialBalanceSummary {
  total_debit: string | number
  total_credit: string | number
  difference: string | number
  is_balanced: boolean
}

interface CreatePeriodForm {
  year: number
  month: number
}

// ─── Helpers ─────────────────────────────────────────

function formatPeriodLabel(year: number, month: number): string {
  return `${year}年${String(month).padStart(2, '0')}月`
}

function parseNumeric(val: string | number): number {
  if (typeof val === 'number') return val
  return parseFloat(val) || 0
}

function groupByYear(periods: Period[]): Map<number, Period[]> {
  const map = new Map<number, Period[]>()
  for (const p of periods) {
    const list = map.get(p.year) || []
    list.push(p)
    map.set(p.year, list)
  }
  // Sort periods within each year by month DESC
  for (const [, list] of map) {
    list.sort((a, b) => b.month - a.month)
  }
  return map
}

// ─── Component ───────────────────────────────────────

export default function PeriodManage() {
  const queryClient = useQueryClient()
  const { can } = usePermission()
  const { currentPeriod } = useCurrentPeriod()

  const canClose = can('period:close')
  const canReopen = can('period:reopen')

  // ─── State ──────────────────────────────────────────

  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [createForm, setCreateForm] = useState<CreatePeriodForm>({
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1,
  })
  const [createError, setCreateError] = useState('')

  // Close dialog
  const [closeTarget, setCloseTarget] = useState<Period | null>(null)
  const [closeTrialBalance, setCloseTrialBalance] = useState<TrialBalanceSummary | null>(null)
  const [closeCheckLoading, setCloseCheckLoading] = useState(false)
  const [closeCheckError, setCloseCheckError] = useState('')

  // Reopen dialog
  const [reopenTarget, setReopenTarget] = useState<Period | null>(null)

  // Expanded trial balance panels
  const [expandedTrialBalance, setExpandedTrialBalance] = useState<Set<string>>(new Set())
  const [trialBalanceCache, setTrialBalanceCache] = useState<Record<string, TrialBalanceSummary>>({})
  const [trialBalanceLoading, setTrialBalanceLoading] = useState<Set<string>>(new Set())

  // Collapsed year groups
  const [collapsedYears, setCollapsedYears] = useState<Set<number>>(new Set())

  // ─── Data Fetching ──────────────────────────────────

  const {
    data: periodsData,
    isLoading,
    error,
  } = useQuery<{ periods: Period[] }>({
    queryKey: ['periods'],
    queryFn: async () => {
      const { data } = await api.get('/periods')
      return data
    },
  })

  const periods = periodsData?.periods || []

  // ─── Mutations ─────────────────────────────────────

  const createMutation = useMutation({
    mutationFn: async (payload: { year: number; month: number }) => {
      const { data } = await api.post('/periods', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['periods'] })
      queryClient.invalidateQueries({ queryKey: ['current-period'] })
      handleCloseCreateDialog()
    },
    onError: (error: any) => {
      setCreateError(error.response?.data?.detail || '创建期间失败')
    },
  })

  const closeMutation = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/periods/${id}/close`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['periods'] })
      queryClient.invalidateQueries({ queryKey: ['current-period'] })
      handleCloseCloseDialog()
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || '结账失败')
    },
  })

  const reopenMutation = useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/periods/${id}/reopen`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['periods'] })
      queryClient.invalidateQueries({ queryKey: ['current-period'] })
      handleCloseReopenDialog()
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || '反结账失败')
    },
  })

  // ─── Create Dialog Handlers ────────────────────────

  const handleOpenCreateDialog = () => {
    const now = new Date()
    setCreateForm({ year: now.getFullYear(), month: now.getMonth() + 1 })
    setCreateError('')
    setShowCreateDialog(true)
  }

  const handleCloseCreateDialog = () => {
    setShowCreateDialog(false)
    setCreateError('')
  }

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setCreateError('')

    if (createForm.year < 2000 || createForm.year > 2100) {
      setCreateError('年份必须在2000-2100之间')
      return
    }

    const exists = periods.some(
      (p) => p.year === createForm.year && p.month === createForm.month,
    )
    if (exists) {
      setCreateError(`${createForm.year}年${createForm.month}月 已存在`)
      return
    }

    createMutation.mutate(createForm)
  }

  // ─── Close Dialog Handlers ─────────────────────────

  const handleOpenCloseDialog = async (period: Period) => {
    setCloseTarget(period)
    setCloseCheckLoading(true)
    setCloseCheckError('')
    setCloseTrialBalance(null)

    try {
      const { data } = await api.get(`/periods/${period.id}/trial-balance`)
      setCloseTrialBalance(data)
    } catch (err: any) {
      setCloseCheckError(err.response?.data?.detail || '无法获取试算平衡数据')
    } finally {
      setCloseCheckLoading(false)
    }
  }

  const handleCloseCloseDialog = () => {
    setCloseTarget(null)
    setCloseTrialBalance(null)
    setCloseCheckError('')
  }

  const handleCloseConfirm = () => {
    if (closeTarget) {
      closeMutation.mutate(closeTarget.id)
    }
  }

  // ─── Reopen Dialog Handlers ────────────────────────

  const handleOpenReopenDialog = (period: Period) => {
    setReopenTarget(period)
  }

  const handleCloseReopenDialog = () => {
    setReopenTarget(null)
  }

  const handleReopenConfirm = () => {
    if (reopenTarget) {
      reopenMutation.mutate(reopenTarget.id)
    }
  }

  // ─── Trial Balance Expand ──────────────────────────

  const toggleTrialBalance = async (periodId: string) => {
    if (expandedTrialBalance.has(periodId)) {
      setExpandedTrialBalance((prev) => {
        const next = new Set(prev)
        next.delete(periodId)
        return next
      })
      return
    }

    if (trialBalanceCache[periodId]) {
      setExpandedTrialBalance((prev) => new Set(prev).add(periodId))
      return
    }

    setTrialBalanceLoading((prev) => new Set(prev).add(periodId))
    try {
      const { data } = await api.get(`/periods/${periodId}/trial-balance`)
      setTrialBalanceCache((prev) => ({ ...prev, [periodId]: data }))
      setExpandedTrialBalance((prev) => new Set(prev).add(periodId))
    } catch {
      // Silently fail — trial balance is supplementary
    } finally {
      setTrialBalanceLoading((prev) => {
        const next = new Set(prev)
        next.delete(periodId)
        return next
      })
    }
  }

  // ─── Year collapse ─────────────────────────────────

  const toggleYear = (year: number) => {
    setCollapsedYears((prev) => {
      const next = new Set(prev)
      if (next.has(year)) next.delete(year)
      else next.add(year)
      return next
    })
  }

  // ─── Grouped and sorted ────────────────────────────

  const grouped = useMemo(() => {
    const map = groupByYear(periods)
    // Sort years DESC
    return [...map.entries()].sort(([a], [b]) => b - a)
  }, [periods])

  // ─── Render helpers ────────────────────────────────

  const isCurrentPeriod = (period: Period) => currentPeriod?.id === period.id

  const renderTrialBalancePanel = (periodId: string) => {
    const tb = trialBalanceCache[periodId]
    const loading = trialBalanceLoading.has(periodId)

    if (loading) {
      return (
        <div className="mt-3 p-3 bg-gray-50 rounded-md">
          <Skeleton className="h-4 w-40" />
        </div>
      )
    }

    if (!tb) return null

    const diff = parseNumeric(tb.difference)

    return (
      <div className="mt-3 p-3 bg-gray-50 rounded-md border">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>
            <span className="text-muted-foreground">借方合计</span>
            <p className="font-mono font-medium mt-0.5">
              {formatAmount(parseNumeric(tb.total_debit))}
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">贷方合计</span>
            <p className="font-mono font-medium mt-0.5">
              {formatAmount(parseNumeric(tb.total_credit))}
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">差额</span>
            <p
              className={cn(
                'font-mono font-medium mt-0.5',
                diff === 0 ? 'text-green-600' : 'text-red-600',
              )}
            >
              {formatAmount(diff)}
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">状态</span>
            <p className="mt-0.5">
              <StatusBadge
                status={tb.is_balanced ? 'pass' : 'fail'}
                label={tb.is_balanced ? '平衡' : '不平衡'}
              />
            </p>
          </div>
        </div>
      </div>
    )
  }

  // ─── Render ─────────────────────────────────────────

  return (
    <div className="p-6">
      {/* ── Header ─────────────────────────────────── */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">会计期间管理</h1>
          <p className="text-sm text-muted-foreground mt-1">管理会计期间、结账与反结账</p>
        </div>
        {canClose && (
          <button
            onClick={handleOpenCreateDialog}
            className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors"
          >
            <Plus size={16} />
            创建期间
          </button>
        )}
      </div>

      {/* ── Loading ────────────────────────────────── */}
      {isLoading && (
        <div className="space-y-4">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="border rounded-lg p-4">
              <Skeleton className="h-6 w-32 mb-3" />
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {Array.from({ length: 3 }, (_, j) => (
                  <Skeleton key={j} variant="card" className="h-28" />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Error ──────────────────────────────────── */}
      {error && !isLoading && (
        <ErrorCard
          message={(error as any)?.response?.data?.detail || '加载会计期间失败'}
          onRetry={() => queryClient.invalidateQueries({ queryKey: ['periods'] })}
        />
      )}

      {/* ── Empty ──────────────────────────────────── */}
      {!isLoading && !error && periods.length === 0 && (
        <EmptyState
          icon={<span className="text-4xl">📅</span>}
          title="暂无会计期间"
          description="请先创建一个会计期间开始使用"
          action={
            canClose
              ? { label: '创建期间', onClick: handleOpenCreateDialog }
              : undefined
          }
        />
      )}

      {/* ── Period Timeline grouped by year ────────── */}
      {!isLoading && !error && periods.length > 0 && (
        <div className="space-y-6">
          {grouped.map(([year, yearPeriods]) => {
            const hasOpen = yearPeriods.some((p) => p.status === PeriodStatus.OPEN)

            return (
              <div key={year} className="border rounded-lg overflow-hidden">
                {/* Year Header */}
                <button
                  onClick={() => toggleYear(year)}
                  className="w-full flex items-center gap-2 px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors border-b"
                >
                  {collapsedYears.has(year) ? (
                    <ChevronRight size={18} className="text-muted-foreground" />
                  ) : (
                    <ChevronDown size={18} className="text-muted-foreground" />
                  )}
                  <span className="text-lg font-semibold">{year}年</span>
                  <span className="text-sm text-muted-foreground ml-2">
                    {yearPeriods.length} 个期间
                  </span>
                  {hasOpen && (
                    <span className="ml-2 inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                      开放中
                    </span>
                  )}
                </button>

                {/* Period Cards */}
                {!collapsedYears.has(year) && (
                  <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {yearPeriods.map((period) => {
                      const isOpen = period.status === PeriodStatus.OPEN
                      const isCurrent = isCurrentPeriod(period)
                      const showTrialBalance = expandedTrialBalance.has(period.id)

                      return (
                        <div
                          key={period.id}
                          className={cn(
                            'border rounded-lg p-4 transition-colors',
                            isCurrent &&
                              'border-l-4 border-l-accent bg-accent/5 shadow-sm',
                          )}
                        >
                          {/* Period Header */}
                          <div className="flex items-start justify-between mb-3">
                            <div>
                              <h3 className="text-base font-semibold">
                                {formatPeriodLabel(period.year, period.month)}
                              </h3>
                              {isCurrent && (
                                <span className="text-xs text-accent font-medium">
                                  当前期间
                                </span>
                              )}
                            </div>
                            <StatusBadge
                              status={period.status}
                              label={isOpen ? '开放' : '已结账'}
                            />
                          </div>

                          {/* Closed info */}
                          {!isOpen && (
                            <div className="text-xs text-muted-foreground space-y-0.5 mb-3">
                              {period.closed_at && (
                                <p>结账时间: {formatDate(period.closed_at)}</p>
                              )}
                              {period.closed_by && (
                                <p>操作人: {period.closed_by}</p>
                              )}
                            </div>
                          )}

                          {/* Action Buttons */}
                          <div className="flex items-center gap-2 mt-3 flex-wrap">
                            {/* Trial Balance Toggle */}
                            <button
                              onClick={() => toggleTrialBalance(period.id)}
                              className={cn(
                                'inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors',
                                'border border-border text-muted-foreground hover:bg-gray-50',
                              )}
                            >
                              <Calculator size={14} />
                              试算平衡
                              {showTrialBalance ? (
                                <ChevronDown size={14} />
                              ) : (
                                <ChevronRight size={14} />
                              )}
                            </button>

                            {/* Close Button */}
                            {isOpen && canClose && (
                              <button
                                onClick={() => handleOpenCloseDialog(period)}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md bg-orange-50 text-orange-700 border border-orange-200 hover:bg-orange-100 transition-colors"
                              >
                                <Lock size={14} />
                                结账
                              </button>
                            )}

                            {/* Reopen Button (admin only) */}
                            {!isOpen && canReopen && (
                              <button
                                onClick={() => handleOpenReopenDialog(period)}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors"
                              >
                                <Unlock size={14} />
                                反结账
                              </button>
                            )}
                          </div>

                          {/* Trial Balance Panel */}
                          {showTrialBalance && renderTrialBalancePanel(period.id)}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* ── Stats ──────────────────────────────────── */}
      {periods.length > 0 && (
        <div className="mt-4 text-sm text-muted-foreground">
          共{' '}
          <span className="font-medium text-foreground">{periods.length}</span>{' '}
          个会计期间，其中
          <span className="font-medium text-green-600">
            {' '}
            {periods.filter((p) => p.status === PeriodStatus.OPEN).length} 个开放
          </span>
          、
          <span className="font-medium text-gray-600">
            {periods.filter((p) => p.status === PeriodStatus.CLOSED).length} 个已结账
          </span>
        </div>
      )}

      {/* ── Create Period Dialog ──────────────────────── */}
      {showCreateDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={handleCloseCreateDialog} />
          <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">创建会计期间</h3>
              <button
                onClick={handleCloseCreateDialog}
                className="p-1 rounded hover:bg-gray-100 text-muted-foreground"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  年份 <span className="text-destructive">*</span>
                </label>
                <input
                  type="number"
                  value={createForm.year}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, year: parseInt(e.target.value) || 0 })
                  }
                  min={2000}
                  max={2100}
                  className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  月份 <span className="text-destructive">*</span>
                </label>
                <select
                  value={createForm.month}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, month: parseInt(e.target.value) })
                  }
                  className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                >
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                    <option key={m} value={m}>
                      {m}月
                    </option>
                  ))}
                </select>
              </div>

              {createError && (
                <div className="text-sm text-destructive bg-red-50 border border-red-200 rounded px-3 py-2">
                  {createError}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={handleCloseCreateDialog}
                  className="px-4 py-2 text-sm font-medium rounded-md border border-border hover:bg-gray-50 transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-4 py-2 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50"
                >
                  {createMutation.isPending ? '创建中...' : '创建'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Close Period Dialog ───────────────────────── */}
      {closeTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={handleCloseCloseDialog}
          />
          <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">结账确认</h3>
              <button
                onClick={handleCloseCloseDialog}
                className="p-1 rounded hover:bg-gray-100 text-muted-foreground"
              >
                <X size={20} />
              </button>
            </div>

            <div className="space-y-4">
              <p className="text-sm">
                确认结账{' '}
                <span className="font-semibold">
                  {closeTarget.year}年{closeTarget.month}月
                </span>
                ？结账后将初始化下期余额。
              </p>

              {/* Trial Balance Check */}
              {closeCheckLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-16 w-full" />
                </div>
              ) : closeCheckError ? (
                <div className="text-sm text-destructive bg-red-50 border border-red-200 rounded px-3 py-2">
                  {closeCheckError}
                </div>
              ) : closeTrialBalance ? (
                <div className="rounded-md border p-3 bg-gray-50">
                  <h4 className="text-sm font-medium mb-2">试算平衡检查</h4>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <span className="text-muted-foreground">借方合计</span>
                      <p className="font-mono font-medium mt-0.5">
                        {formatAmount(parseNumeric(closeTrialBalance.total_debit))}
                      </p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">贷方合计</span>
                      <p className="font-mono font-medium mt-0.5">
                        {formatAmount(parseNumeric(closeTrialBalance.total_credit))}
                      </p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">差额</span>
                      <p
                        className={cn(
                          'font-mono font-medium mt-0.5',
                          parseNumeric(closeTrialBalance.difference) === 0
                            ? 'text-green-600'
                            : 'text-red-600',
                        )}
                      >
                        {formatAmount(parseNumeric(closeTrialBalance.difference))}
                      </p>
                    </div>
                  </div>
                  <div className="mt-2">
                    {closeTrialBalance.is_balanced ? (
                      <div className="flex items-center gap-1.5 text-sm text-green-600">
                        <CheckCircle size={16} />
                        试算平衡 — 可以安全结账
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 text-sm text-red-600">
                        <AlertTriangle size={16} />
                        试算不平衡 — 结账可能存在风险
                      </div>
                    )}
                  </div>
                </div>
              ) : null}
            </div>

            <div className="flex justify-end gap-3 mt-6 pt-4 border-t">
              <button
                onClick={handleCloseCloseDialog}
                className="px-4 py-2 text-sm font-medium rounded-md border border-border hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleCloseConfirm}
                disabled={closeMutation.isPending}
                className="px-4 py-2 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50"
              >
                {closeMutation.isPending ? '处理中...' : '确认结账'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Reopen Period Dialog ──────────────────────── */}
      <ConfirmDialog
        open={!!reopenTarget}
        title="反结账确认"
        message={
          reopenTarget
            ? `确认反结账 ${reopenTarget.year}年${reopenTarget.month}月？将删除下期结转余额。`
            : ''
        }
        confirmLabel="确认反结账"
        cancelLabel="取消"
        variant="danger"
        onConfirm={handleReopenConfirm}
        onCancel={handleCloseReopenDialog}
      />
    </div>
  )
}
