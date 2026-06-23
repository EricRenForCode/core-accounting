import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import {
  useQuery,
  useMutation,
  useQueryClient,
  keepPreviousData,
} from '@tanstack/react-query'
import api from '@/lib/api'
import { FileText, Plus, Pencil, Trash2, Copy } from 'lucide-react'
import { ConfirmDialog } from '@/components/ConfirmDialog'

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
  created_at: string
  updated_at: string
}

interface PaginatedTemplates {
  items: VoucherTemplate[]
  total: number
  page: number
  page_size: number
  pages: number
}

// ─── Queries & Mutations ────────────────────────────

function useTemplates(page: number) {
  return useQuery<PaginatedTemplates>({
    queryKey: ['voucher-templates', page],
    queryFn: async () => {
      const { data } = await api.get<PaginatedTemplates>('/voucher-templates', {
        params: { page, page_size: 20 },
      })
      return data
    },
    placeholderData: keepPreviousData,
  })
}

function useDeleteTemplate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/voucher-templates/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['voucher-templates'] })
    },
  })
}

// ─── Component ──────────────────────────────────────

export default function VoucherTemplateList() {
  const [page, setPage] = useState(1)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const navigate = useNavigate()

  const { data, isLoading, isError } = useTemplates(page)
  const deleteMutation = useDeleteTemplate()

  const templates = data?.items || []
  const total = data?.total || 0
  const pages = data?.pages || 1

  function handleDelete() {
    if (!deleteId) return
    deleteMutation.mutate(deleteId)
    setDeleteId(null)
  }

  function handleUseTemplate(template: VoucherTemplate) {
    // Navigate to voucher creation with template data via URL state
    navigate({
      to: '/vouchers/new',
      search: { templateId: template.id },
    })
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">凭证模板</h2>
          <p className="text-sm text-muted-foreground mt-1">
            管理常用凭证模板，从模板快速生成凭证
          </p>
        </div>
        <button
          onClick={() => navigate({ to: '/vouchers/templates/new' })}
          className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors"
        >
          <Plus size={16} />
          新建模板
        </button>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          <p>加载中...</p>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-lg border bg-red-50 p-8 text-center">
          <p className="text-red-600 font-medium">加载模板失败</p>
          <p className="text-sm text-red-500 mt-1">请检查网络连接后重试</p>
        </div>
      )}

      {/* Empty */}
      {!isLoading && !isError && templates.length === 0 && (
        <div className="rounded-lg border bg-card p-12 text-center">
          <FileText size={48} className="mx-auto text-muted-foreground/40 mb-4" />
          <p className="text-lg text-muted-foreground">暂无模板</p>
          <p className="text-sm text-muted-foreground mt-1">
            创建模板后可快速生成常用凭证
          </p>
        </div>
      )}

      {/* Template Grid */}
      {!isLoading && templates.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {templates.map((template) => (
              <div
                key={template.id}
                className="rounded-lg border bg-card hover:shadow-sm transition-shadow"
              >
                <div className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold truncate">{template.name}</h3>
                      {template.category && (
                        <span className="inline-block mt-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-muted-foreground">
                          {template.category}
                        </span>
                      )}
                    </div>
                    {!template.is_enabled && (
                      <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                        已禁用
                      </span>
                    )}
                  </div>

                  {template.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
                      {template.description}
                    </p>
                  )}

                  <div className="flex items-center gap-1 text-xs text-muted-foreground mb-3">
                    <FileText size={12} />
                    <span>{template.entries.length} 条分录</span>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 pt-3 border-t">
                    <button
                      onClick={() => handleUseTemplate(template)}
                      className="flex items-center gap-1 rounded-md bg-green-50 border border-green-200 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100 transition-colors"
                    >
                      <Copy size={12} />
                      生成凭证
                    </button>
                    <button
                      onClick={() =>
                        navigate({
                          to: '/vouchers/templates/$templateId',
                          params: { templateId: template.id },
                        })
                      }
                      className="flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-gray-50 transition-colors"
                    >
                      <Pencil size={12} />
                      编辑
                    </button>
                    <button
                      onClick={() => setDeleteId(template.id)}
                      className="flex items-center gap-1 rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 transition-colors"
                    >
                      <Trash2 size={12} />
                      删除
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex items-center justify-between mt-6">
              <p className="text-sm text-muted-foreground">
                共 {total} 个模板
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-40"
                >
                  上一页
                </button>
                <span className="text-sm text-muted-foreground">
                  {page} / {pages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(pages, p + 1))}
                  disabled={page >= pages}
                  className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-40"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Delete Confirm */}
      <ConfirmDialog
        open={!!deleteId}
        title="删除模板"
        description="确定要删除此模板吗？此操作不可撤销。"
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
        loading={deleteMutation.isPending}
      />
    </div>
  )
}
