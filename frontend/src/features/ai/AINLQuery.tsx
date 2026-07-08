import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'
import { Search, Send, Loader2, Clock, Database, RotateCcw } from 'lucide-react'

interface QueryResult {
  conversation_id: string
  question: string
  sql: string
  columns: string[]
  rows: unknown[][]
  row_count: number
  execution_time_ms: number
}

export default function AINLQueryPage() {
  const [question, setQuestion] = useState('')
  // Multi-turn: keep every answered turn + the conversation id so follow-up
  // questions ("那上个月呢") resolve against earlier context (P2 连续追问).
  const [turns, setTurns] = useState<QueryResult[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: async (q: string) => {
      const { data } = await api.post('/ai/query', {
        question: q,
        ...(conversationId ? { conversation_id: conversationId } : {}),
      })
      return data as QueryResult
    },
    onSuccess: (data) => {
      setTurns((prev) => [...prev, data])
      setConversationId(data.conversation_id)
      setQuestion('')
      setError('')
    },
    onError: (err: unknown) => {
      const data = (err as {
        response?: { data?: { detail?: string; error?: { message?: string } } }
      })?.response?.data
      setError(data?.detail || data?.error?.message || '查询失败')
    },
  })

  const handleQuery = () => {
    if (!question.trim() || question.length > 500) return
    setError('')
    mutation.mutate(question.trim())
  }

  const handleReset = () => {
    setTurns([])
    setConversationId(null)
    setError('')
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Search className="h-5 w-5 text-primary" />
          自然语言查询
        </h2>
        {turns.length > 0 && (
          <button
            onClick={handleReset}
            className="flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-gray-50"
          >
            <RotateCcw className="h-3 w-3" />
            新对话
          </button>
        )}
      </div>

      <p className="text-sm text-muted-foreground">
        用中文描述你想查询的数据，AI 会自动生成并执行 SQL
        查询（只读，安全限制已完成）。同一对话内可以连续追问。
      </p>

      {/* Answered turns */}
      {turns.map((result, ti) => (
        <div key={ti} className="space-y-2">
          <div className="text-sm font-medium">
            <span className="text-muted-foreground mr-2">Q{ti + 1}:</span>
            {result.question}
          </div>

          {/* SQL display (collapsible) */}
          <details className="rounded-lg border bg-muted/30 p-3">
            <summary className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
              <Database className="h-3 w-3" />
              生成的 SQL
              <span className="ml-auto flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {result.execution_time_ms}ms
              </span>
            </summary>
            <pre className="mt-2 text-xs font-mono bg-background rounded p-2 overflow-x-auto">
              {result.sql}
            </pre>
          </details>

          {/* Results table */}
          <div className="rounded-lg border overflow-hidden">
            <div className="px-3 py-2 bg-muted/50 text-xs text-muted-foreground">
              返回 {result.row_count} 行
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/30 border-b">
                    {result.columns.map((col, i) => (
                      <th
                        key={i}
                        className="py-1.5 px-3 text-left font-medium text-xs"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row, ri) => (
                    <tr
                      key={ri}
                      className="border-b last:border-0 hover:bg-gray-50/30"
                    >
                      {row.map((cell, ci) => (
                        <td key={ci} className="py-1 px-3 text-xs tabular-nums">
                          {String(cell ?? '—')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ))}

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Input */}
      <div className="rounded-lg border p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
            placeholder={
              turns.length > 0
                ? '继续追问，例如: "那上个月呢"'
                : '例如: "本月管理费用超过1万的科目有哪些"'
            }
            className="flex-1 rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            maxLength={500}
            disabled={mutation.isPending}
          />
          <button
            onClick={handleQuery}
            disabled={
              mutation.isPending || !question.trim() || question.length > 500
            }
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {mutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {question.length}/500 字符
        </p>
      </div>
    </div>
  )
}
