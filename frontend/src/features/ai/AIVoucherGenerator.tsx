import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'
import { useCurrentPeriod } from '@/hooks/useCurrentPeriod'
import { Sparkles, Send, Loader2, CheckCircle, XCircle } from 'lucide-react'

interface AIEntry {
  row_number: number
  account: { id: string; code: string; name: string }
  summary: string
  debit_amount: number
  credit_amount: number
  auxiliaries: { aux_type: string; entity_code?: string }[]
}

interface AIVoucherResult {
  conversation_id: string
  entries: AIEntry[]
  is_balanced: boolean
  matched_accounts: string[]
  ai_notes: string
}

function fmt(n: number): string {
  return n.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export default function AIVoucherGeneratorPage() {
  const { currentPeriod } = useCurrentPeriod()
  const [description, setDescription] = useState('')
  const [result, setResult] = useState<AIVoucherResult | null>(null)
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: async (desc: string) => {
      const { data } = await api.post('/ai/voucher/generate', {
        description: desc,
        period_id: currentPeriod?.id,
      })
      return data as AIVoucherResult
    },
    onSuccess: (data) => {
      setResult(data)
      setError('')
    },
    onError: (err: unknown) => {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || 'AI 生成失败',
      )
    },
  })

  const handleGenerate = () => {
    if (!description.trim()) return
    setResult(null)
    setError('')
    mutation.mutate(description.trim())
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-primary" />
        智能凭证生成
      </h2>

      {/* Input */}
      <div className="rounded-lg border p-4">
        <label className="block text-sm font-medium mb-2">
          用自然语言描述交易
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="例如：支付张三差旅费5000元，从工商银行转出"
          className="w-full rounded-md border px-3 py-2 text-sm min-h-[80px] focus:outline-none focus:ring-2 focus:ring-primary/30"
          disabled={mutation.isPending}
        />
        <div className="mt-3 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            当前期间: {currentPeriod?.year}年{currentPeriod?.month}月
          </span>
          <button
            onClick={handleGenerate}
            disabled={mutation.isPending || !description.trim() || !currentPeriod}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                生成中...
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                生成分录
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

      {/* Result */}
      {result && (
        <div className="space-y-4">
          {/* Balance indicator */}
          <div
            className={`rounded-md px-3 py-2 text-sm ${
              result.is_balanced
                ? 'bg-green-50 border border-green-200 text-green-700'
                : 'bg-red-50 border border-red-200 text-red-700'
            }`}
          >
            {result.is_balanced ? (
              <span className="flex items-center gap-1">
                <CheckCircle className="h-4 w-4" /> 分录平衡
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <XCircle className="h-4 w-4" /> 分录不平衡
              </span>
            )}
          </div>

          {/* AI notes */}
          {result.ai_notes && (
            <div className="rounded-md bg-blue-50 border border-blue-200 px-3 py-2 text-sm text-blue-700">
              💡 {result.ai_notes}
            </div>
          )}

          {/* Matched accounts */}
          <div className="text-sm text-muted-foreground">
            匹配科目: {result.matched_accounts.join(', ')}
          </div>

          {/* Entry table */}
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 border-b">
                  <th className="py-2 pl-4 text-left w-8">#</th>
                  <th className="py-2 text-left">科目</th>
                  <th className="py-2 text-left">摘要</th>
                  <th className="py-2 pr-3 text-right w-28">借方</th>
                  <th className="py-2 pr-2 text-right w-28">贷方</th>
                </tr>
              </thead>
              <tbody>
                {result.entries.map((entry, i) => (
                  <tr key={i} className="border-b last:border-0 hover:bg-gray-50/30">
                    <td className="py-1.5 pl-4 text-muted-foreground">
                      {entry.row_number}
                    </td>
                    <td className="py-1.5">
                      <span className="font-medium">{entry.account.name}</span>
                      <span className="text-xs text-muted-foreground ml-1">
                        {entry.account.code}
                      </span>
                    </td>
                    <td className="py-1.5 text-muted-foreground text-xs">
                      {entry.summary}
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">
                      {entry.debit_amount > 0 ? fmt(entry.debit_amount) : ''}
                    </td>
                    <td className="py-1.5 pr-2 text-right tabular-nums">
                      {entry.credit_amount > 0 ? fmt(entry.credit_amount) : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t font-medium bg-muted/10">
                  <td colSpan={3} className="py-2 pl-4 text-right">
                    合计
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {fmt(
                      result.entries.reduce(
                        (s, e) => s + (e.debit_amount || 0),
                        0,
                      ),
                    )}
                  </td>
                  <td className="py-2 pr-2 text-right tabular-nums">
                    {fmt(
                      result.entries.reduce(
                        (s, e) => s + (e.credit_amount || 0),
                        0,
                      ),
                    )}
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
