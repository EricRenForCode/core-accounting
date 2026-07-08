import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'
import { Sparkles, Send, X, Loader2, RotateCcw } from 'lucide-react'

interface QueryResult {
  conversation_id: string
  question: string
  sql: string
  columns: string[]
  rows: unknown[][]
  row_count: number
  execution_time_ms: number
}

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  result?: QueryResult
}

const MAX_PREVIEW_ROWS = 5

/** Global floating AI assistant (右下角悬浮面板, spec §3.12 / v3 P2).
 *
 * Wraps /ai/query so users can ask data questions from any page without
 * leaving their workflow. Multi-turn: conversation_id is carried across
 * questions until the user resets.
 */
export function AIChatPanel() {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages, open])

  const mutation = useMutation({
    mutationFn: async (q: string) => {
      const { data } = await api.post('/ai/query', {
        question: q,
        ...(conversationId ? { conversation_id: conversationId } : {}),
      })
      return data as QueryResult
    },
    onSuccess: (data) => {
      setConversationId(data.conversation_id)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `返回 ${data.row_count} 行（${data.execution_time_ms}ms）`,
          result: data,
        },
      ])
    },
    onError: (err: unknown) => {
      const data = (err as {
        response?: { data?: { detail?: string; error?: { message?: string } } }
      })?.response?.data
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: data?.detail || data?.error?.message || '查询失败，请换个问法试试',
        },
      ])
    },
  })

  const handleSend = () => {
    const q = input.trim()
    if (!q || q.length > 500 || mutation.isPending) return
    setMessages((prev) => [...prev, { role: 'user', text: q }])
    setInput('')
    mutation.mutate(q)
  }

  const handleReset = () => {
    setMessages([])
    setConversationId(null)
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label="打开 AI 助手"
        className="fixed bottom-5 right-5 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-transform hover:scale-105"
      >
        <Sparkles className="h-5 w-5" />
      </button>
    )
  }

  return (
    <div className="fixed bottom-5 right-5 z-50 flex h-[480px] w-[380px] flex-col rounded-xl border bg-background shadow-2xl">
      {/* Header */}
      <div className="flex items-center gap-2 border-b px-4 py-2.5">
        <Sparkles className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold">AI 数据助手</span>
        <span className="text-[10px] text-muted-foreground">只读查询</span>
        <div className="ml-auto flex items-center gap-1">
          {messages.length > 0 && (
            <button
              onClick={handleReset}
              aria-label="新对话"
              className="rounded p-1 hover:bg-muted"
            >
              <RotateCcw className="h-3.5 w-3.5 text-muted-foreground" />
            </button>
          )}
          <button
            onClick={() => setOpen(false)}
            aria-label="关闭"
            className="rounded p-1 hover:bg-muted"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
        {messages.length === 0 && (
          <div className="pt-10 text-center text-xs text-muted-foreground">
            用中文提问账套数据，例如
            <div className="mt-2 space-y-1">
              {['本月管理费用多少', '库存现金余额', '未审核的凭证有几张'].map(
                (s) => (
                  <button
                    key={s}
                    onClick={() => setInput(s)}
                    className="block w-full rounded-md border border-dashed px-2 py-1 hover:bg-muted/50"
                  >
                    {s}
                  </button>
                ),
              )}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-lg bg-primary px-3 py-1.5 text-xs text-primary-foreground">
                {m.text}
              </div>
            </div>
          ) : (
            <div key={i} className="space-y-1.5">
              <div className="max-w-[95%] rounded-lg bg-muted px-3 py-1.5 text-xs">
                {m.text}
              </div>
              {m.result && m.result.rows.length > 0 && (
                <div className="overflow-x-auto rounded-md border">
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr className="border-b bg-muted/40">
                        {m.result.columns.map((c, ci) => (
                          <th key={ci} className="px-2 py-1 text-left font-medium">
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {m.result.rows.slice(0, MAX_PREVIEW_ROWS).map((row, ri) => (
                        <tr key={ri} className="border-b last:border-0">
                          {row.map((cell, ci) => (
                            <td key={ci} className="px-2 py-1 tabular-nums">
                              {String(cell ?? '—')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {m.result.rows.length > MAX_PREVIEW_ROWS && (
                    <div className="px-2 py-1 text-[10px] text-muted-foreground">
                      仅显示前 {MAX_PREVIEW_ROWS} 行,共 {m.result.row_count} 行
                    </div>
                  )}
                </div>
              )}
              {m.result && (
                <details className="text-[10px] text-muted-foreground">
                  <summary className="cursor-pointer">查看 SQL</summary>
                  <pre className="mt-1 overflow-x-auto rounded bg-muted/40 p-1.5 font-mono">
                    {m.result.sql}
                  </pre>
                </details>
              )}
            </div>
          ),
        )}

        {mutation.isPending && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            正在生成查询…
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex items-center gap-2 border-t p-2.5">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder={conversationId ? '继续追问…' : '输入问题…'}
          maxLength={500}
          className="flex-1 rounded-md border px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary/30"
          disabled={mutation.isPending}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || mutation.isPending}
          aria-label="发送"
          className="rounded-md bg-primary p-2 text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
