import { useState, useEffect } from 'react'
import { useNavigate, useParams } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { ArrowLeft, Plus, Trash2, Save } from 'lucide-react'

interface TemplateEntry {
  account_id: string
  summary: string
  dc_side: 'debit' | 'credit'
  auxiliaries: Array<{
    aux_type: string
    department_id?: string
    individual_id?: string
    counterparty_id?: string
    project_id?: string
  }>
}

interface VoucherTemplate {
  id: string
  name: string
  description?: string
  category?: string
  entries: TemplateEntry[]
  is_enabled: boolean
}

interface EntryRow {
  key: string
  account_id: string
  summary: string
  dc_side: 'debit' | 'credit'
}

function newEntry(): EntryRow {
  return {
    key: crypto.randomUUID(),
    account_id: '',
    summary: '',
    dc_side: 'debit',
  }
}

// ─── Queries & Mutations ────────────────────────────

function useTemplate(id: string) {
  return useQuery<VoucherTemplate>({
    queryKey: ['voucher-template', id],
    queryFn: async () => {
      const { data } = await api.get<VoucherTemplate>(`/voucher-templates/${id}`)
      return data
    },
    enabled: !!id,
  })
}

function useCreateTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: {
      name: string
      description?: string
      category?: string
      entries: TemplateEntry[]
      is_enabled: boolean
    }) => {
      const { data } = await api.post('/voucher-templates', body)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['voucher-templates'] })
    },
  })
}

function useUpdateTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      body,
    }: {
      id: string
      body: { name?: string; description?: string; category?: string; entries?: TemplateEntry[]; is_enabled?: boolean }
    }) => {
      const { data } = await api.put(`/voucher-templates/${id}`, body)
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['voucher-templates'] })
      queryClient.invalidateQueries({ queryKey: ['voucher-template', variables.id] })
    },
  })
}

// ─── Component ──────────────────────────────────────

export default function VoucherTemplateForm() {
  const { templateId } = useParams({ from: '/vouchers/templates/$templateId' })
  const isEdit = !!templateId
  const navigate = useNavigate()

  const { data: existing, isLoading: isLoadingExisting } = useTemplate(templateId || '')
  const createMutation = useCreateTemplate()
  const updateMutation = useUpdateTemplate()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('')
  const [isEnabled, setIsEnabled] = useState(true)
  const [entries, setEntries] = useState<EntryRow[]>([newEntry()])
  const [error, setError] = useState('')

  // Initialize from existing template
  useEffect(() => {
    if (existing) {
      setName(existing.name)
      setDescription(existing.description || '')
      setCategory(existing.category || '')
      setIsEnabled(existing.is_enabled)
      setEntries(
        existing.entries.map((e) => ({
          key: crypto.randomUUID(),
          account_id: e.account_id,
          summary: e.summary || '',
          dc_side: e.dc_side || 'debit',
        })),
      )
    }
  }, [existing])

  function addEntry() {
    setEntries([...entries, newEntry()])
  }

  function removeEntry(key: string) {
    if (entries.length <= 1) return
    setEntries(entries.filter((e) => e.key !== key))
  }

  function updateEntry(key: string, field: keyof EntryRow, value: string) {
    setEntries(
      entries.map((e) =>
        e.key === key ? { ...e, [field]: value } : e,
      ),
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (!name.trim()) {
      setError('请输入模板名称')
      return
    }

    if (entries.length === 0) {
      setError('请至少添加一条分录')
      return
    }

    // Validate entries
    for (const entry of entries) {
      if (!entry.account_id) {
        setError('请为所有分录选择科目')
        return
      }
    }

    const templateEntries: TemplateEntry[] = entries.map((e) => ({
      account_id: e.account_id,
      summary: e.summary,
      dc_side: e.dc_side,
      auxiliaries: [],
    }))

    const body = {
      name: name.trim(),
      description: description.trim() || undefined,
      category: category.trim() || undefined,
      entries: templateEntries,
      is_enabled: isEnabled,
    }

    try {
      if (isEdit && templateId) {
        await updateMutation.mutateAsync({ id: templateId, body })
      } else {
        await createMutation.mutateAsync(body)
      }
      navigate({ to: '/vouchers/templates' })
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || '保存失败'
      setError(msg)
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  if (isEdit && isLoadingExisting) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <p className="text-muted-foreground">加载中...</p>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      {/* Back nav */}
      <button
        onClick={() => navigate({ to: '/vouchers/templates' })}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ArrowLeft size={16} />
        返回模板列表
      </button>

      <h2 className="text-2xl font-bold mb-6">
        {isEdit ? '编辑模板' : '新建模板'}
      </h2>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Error */}
        {error && (
          <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
            {error}
          </div>
        )}

        {/* Name */}
        <div>
          <label className="block text-sm font-medium mb-1">
            模板名称 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：差旅费报销"
            className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
        </div>

        {/* Category & Enabled */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">分类</label>
            <input
              type="text"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="例如：费用报销"
              className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
          <div className="flex items-end pb-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isEnabled}
                onChange={(e) => setIsEnabled(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm font-medium">启用</span>
            </label>
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium mb-1">说明</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="模板使用说明..."
            rows={2}
            className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent resize-y"
          />
        </div>

        {/* Entries */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium">
              模板分录 <span className="text-red-500">*</span>
            </label>
            <button
              type="button"
              onClick={addEntry}
              className="flex items-center gap-1 text-xs text-accent hover:underline"
            >
              <Plus size={14} />
              添加分录
            </button>
          </div>

          <div className="space-y-3">
            {entries.map((entry, idx) => (
              <div
                key={entry.key}
                className="flex items-start gap-2 rounded-md border bg-gray-50/50 p-3"
              >
                <span className="text-xs text-muted-foreground mt-2 w-6 text-center">
                  {idx + 1}
                </span>
                <div className="flex-1 space-y-2">
                  <input
                    type="text"
                    value={entry.account_id}
                    onChange={(e) => updateEntry(entry.key, 'account_id', e.target.value)}
                    placeholder="科目 ID（例如：科目UUID）"
                    className="w-full rounded-md border bg-white px-2 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-accent"
                  />
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={entry.summary}
                      onChange={(e) => updateEntry(entry.key, 'summary', e.target.value)}
                      placeholder="摘要"
                      className="flex-1 rounded-md border bg-white px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                    <select
                      value={entry.dc_side}
                      onChange={(e) =>
                        updateEntry(entry.key, 'dc_side', e.target.value)
                      }
                      className="w-24 rounded-md border bg-white px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-accent"
                    >
                      <option value="debit">借方</option>
                      <option value="credit">贷方</option>
                    </select>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => removeEntry(entry.key)}
                  disabled={entries.length <= 1}
                  className="mt-2 p-1 text-red-400 hover:text-red-600 disabled:opacity-30 transition-colors"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center gap-3 pt-4">
          <button
            type="submit"
            disabled={isPending}
            className="flex items-center gap-1.5 rounded-md bg-accent px-6 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50 transition-colors"
          >
            <Save size={16} />
            {isPending ? '保存中...' : '保存模板'}
          </button>
          <button
            type="button"
            onClick={() => navigate({ to: '/vouchers/templates' })}
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            取消
          </button>
        </div>
      </form>
    </div>
  )
}
