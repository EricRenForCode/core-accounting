import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { useCurrentPeriod } from '@/hooks/useCurrentPeriod'
import { Skeleton } from '@/components/Skeleton'
import { ErrorCard } from '@/components/ErrorCard'
import { Play, CheckCircle, XCircle, AlertTriangle, Loader2 } from 'lucide-react'

interface CarryTemplate {
  id: string
  name: string
  description: string
  rules: Record<string, unknown>
  sort_order: number
  is_enabled: boolean
}

interface CarryForwardResult {
  template_id: string
  template_name: string
  voucher_no: string
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

const STATUS_BG: Record<string, string> = {
  pass: 'bg-green-50 border-green-200',
  warn: 'bg-amber-50 border-amber-200',
  fail: 'bg-red-50 border-red-200',
}

export default function CarryForwardPage() {
  const { currentPeriod, isLoading: periodLoading } = useCurrentPeriod()
  const queryClient = useQueryClient()
  const [selectedTemplates, setSelectedTemplates] = useState<Set<string>>(
    new Set(),
  )
  const [executing, setExecuting] = useState(false)
  const [results, setResults] = useState<CarryForwardResult[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load templates
  const {
    data: templates,
    isLoading: templatesLoading,
    error: templatesError,
  } = useQuery<CarryTemplate[]>({
    queryKey: ['carry-templates'],
    queryFn: async () => {
      const { data } = await api.get('/carry-forward/templates')
      return data
    },
  })

  // Load pre-close check
  const {
    data: checkData,
    isLoading: checkLoading,
  } = useQuery<CheckResponse>({
    queryKey: ['period-check', currentPeriod?.id],
    queryFn: async () => {
      const { data } = await api.get('/carry-forward/check', {
        params: { period_id: currentPeriod?.id },
      })
      return data
    },
    enabled: !!currentPeriod?.id,
  })

  const executeMutation = useMutation({
    mutationFn: async (templateIds: string[]) => {
      const { data } = await api.post('/carry-forward/execute', {
        period_id: currentPeriod?.id,
        template_ids: templateIds,
      })
      return data as { executed: number; details: CarryForwardResult[] }
    },
  })

  const handleToggleTemplate = (id: string) => {
    const next = new Set(selectedTemplates)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    setSelectedTemplates(next)
  }

  const handleExecute = async () => {
    if (selectedTemplates.size === 0) return
    setExecuting(true)
    setError(null)
    setResults(null)
    try {
      const res = await executeMutation.mutateAsync(
        Array.from(selectedTemplates),
      )
      setResults(res.details)
      queryClient.invalidateQueries({ queryKey: ['period-check'] })
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || '结转执行失败',
      )
    } finally {
      setExecuting(false)
    }
  }

  if (periodLoading || templatesLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (templatesError) {
    return (
      <div className="p-6">
        <ErrorCard
          title="加载结转模板失败"
          message={(templatesError as Error)?.message || '请稍后重试'}
        />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h2 className="text-xl font-bold">期末结转</h2>

      {/* Pre-close check */}
      {checkData && (
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
                  className={`flex items-center gap-2 rounded px-3 py-1.5 text-sm border ${STATUS_BG[check.status]}`}
                >
                  <Icon
                    className={`h-4 w-4 ${STATUS_COLOR[check.status]}`}
                  />
                  <span className="font-medium">{check.name}</span>
                  <span className="text-muted-foreground">— {check.detail}</span>
                </div>
              )
            })}
          </div>
          {checkData.can_close && (
            <div className="mt-3 rounded bg-green-50 px-3 py-1.5 text-sm text-green-700">
              ✓ 所有检查通过，可以执行结转并结账
            </div>
          )}
        </div>
      )}

      {/* Template selection */}
      <div className="rounded-lg border p-4">
        <h3 className="font-semibold text-sm mb-3">选择结转模板</h3>
        {!templates || templates.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            暂无可用结转模板。请在系统管理中配置结转模板。
          </p>
        ) : (
          <div className="space-y-2">
            {templates.map((tmpl) => (
              <label
                key={tmpl.id}
                className={`flex items-center gap-3 rounded border px-3 py-2 cursor-pointer transition-colors ${
                  selectedTemplates.has(tmpl.id)
                    ? 'border-primary bg-primary/5'
                    : 'hover:bg-muted/50'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedTemplates.has(tmpl.id)}
                  onChange={() => handleToggleTemplate(tmpl.id)}
                  className="rounded"
                  disabled={executing}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{tmpl.name}</p>
                  {tmpl.description && (
                    <p className="text-xs text-muted-foreground truncate">
                      {tmpl.description}
                    </p>
                  )}
                </div>
                <span className="text-xs text-muted-foreground">
                  顺序: {tmpl.sort_order}
                </span>
              </label>
            ))}
          </div>
        )}

        {/* Execute button */}
        <div className="mt-4">
          <button
            onClick={handleExecute}
            disabled={
              executing ||
              selectedTemplates.size === 0 ||
              !currentPeriod?.id
            }
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {executing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                执行中...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                执行结转 ({selectedTemplates.size} 项)
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Results */}
      {results && results.length > 0 && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4">
          <h3 className="font-semibold text-sm text-green-800 mb-2">
            ✅ 结转执行完成 — 共 {results.length} 项
          </h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-green-700">
                <th className="py-1">模板</th>
                <th className="py-1">生成凭证号</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i} className="border-t border-green-200">
                  <td className="py-1">{r.template_name}</td>
                  <td className="py-1 font-mono text-green-900">
                    {r.voucher_no}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* No results */}
      {results && results.length === 0 && (
        <div className="rounded-lg border p-4 text-center text-sm text-muted-foreground">
          未生成结转凭证 — 所选模板可能无需结转或余额为零
        </div>
      )}
    </div>
  )
}
