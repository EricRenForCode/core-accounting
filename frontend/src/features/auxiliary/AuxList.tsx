import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { Plus, Pencil, Trash2, Search } from 'lucide-react'

interface AuxEntity {
  id: string
  code: string
  name: string
  is_enabled: boolean
  created_at: string
}

interface PaginatedAux {
  items: AuxEntity[]
  total: number
  page: number
  page_size: number
  pages: number
}

type AuxType = 'departments' | 'individuals' | 'counterparties' | 'projects'

const TYPE_LABELS: Record<AuxType, { label: string; codeLabel: string; nameLabel: string }> = {
  departments: { label: '部门', codeLabel: '部门编码', nameLabel: '部门名称' },
  individuals: { label: '个人', codeLabel: '个人编码', nameLabel: '个人名称' },
  counterparties: { label: '往来单位', codeLabel: '单位编码', nameLabel: '单位名称' },
  projects: { label: '项目', codeLabel: '项目编码', nameLabel: '项目名称' },
}

export default function AuxList() {
  const queryClient = useQueryClient()
  const [auxType, setAuxType] = useState<AuxType>('departments')
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<AuxEntity | null>(null)
  const [formCode, setFormCode] = useState('')
  const [formName, setFormName] = useState('')
  const [formEnabled, setFormEnabled] = useState(true)
  const [formError, setFormError] = useState('')

  const labels = TYPE_LABELS[auxType]

  // Query list
  const { data, isLoading, isError } = useQuery<PaginatedAux>({
    queryKey: ['auxiliaries', auxType, page, search],
    queryFn: async () => {
      const params: Record<string, string | number> = {
        page,
        page_size: 20,
      }
      if (search) params.search = search
      const { data } = await api.get<PaginatedAux>(
        `/auxiliaries/${auxType}`,
        { params },
      )
      return data
    },
  })

  // Create mutation
  const createMut = useMutation({
    mutationFn: (body: { code: string; name: string; is_enabled: boolean }) =>
      api.post(`/auxiliaries/${auxType}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auxiliaries', auxType] })
      resetForm()
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || '创建失败'
      setFormError(msg)
    },
  })

  // Update mutation
  const updateMut = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string
      body: { code?: string; name?: string; is_enabled?: boolean }
    }) => api.put(`/auxiliaries/${auxType}/${id}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auxiliaries', auxType] })
      resetForm()
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || '更新失败'
      setFormError(msg)
    },
  })

  // Delete mutation
  const deleteMut = useMutation({
    mutationFn: (id: string) =>
      api.delete(`/auxiliaries/${auxType}/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auxiliaries', auxType] })
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || '删除失败'
      alert(msg)
    },
  })

  function resetForm() {
    setShowForm(false)
    setEditing(null)
    setFormCode('')
    setFormName('')
    setFormEnabled(true)
    setFormError('')
  }

  function openCreate() {
    setEditing(null)
    setFormCode('')
    setFormName('')
    setFormEnabled(true)
    setFormError('')
    setShowForm(true)
  }

  function openEdit(entity: AuxEntity) {
    setEditing(entity)
    setFormCode(entity.code)
    setFormName(entity.name)
    setFormEnabled(entity.is_enabled)
    setFormError('')
    setShowForm(true)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError('')

    if (!formCode.trim() || !formName.trim()) {
      setFormError('编码和名称不能为空')
      return
    }

    if (editing) {
      updateMut.mutate({
        id: editing.id,
        body: {
          code: formCode.trim(),
          name: formName.trim(),
          is_enabled: formEnabled,
        },
      })
    } else {
      createMut.mutate({
        code: formCode.trim(),
        name: formName.trim(),
        is_enabled: formEnabled,
      })
    }
  }

  function changeType(type: AuxType) {
    setAuxType(type)
    setPage(1)
    setSearch('')
    resetForm()
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">辅助核算档案</h2>
          <p className="text-sm text-muted-foreground mt-1">
            管理部门、个人、往来单位和项目档案
          </p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors"
        >
          <Plus size={16} />
          新增{labels.label}
        </button>
      </div>

      {/* Type Tabs */}
      <div className="flex gap-1 mb-4 border-b">
        {(Object.keys(TYPE_LABELS) as AuxType[]).map((type) => (
          <button
            key={type}
            onClick={() => changeType(type)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              auxType === type
                ? 'border-accent text-accent'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {TYPE_LABELS[type].label}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
            className="w-full rounded-md border pl-9 pr-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            placeholder={`搜索${labels.label}编码或名称...`}
          />
        </div>
      </div>

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-bold mb-4">
              {editing ? `编辑${labels.label}` : `新增${labels.label}`}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              {formError && (
                <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-600">
                  {formError}
                </div>
              )}
              <div>
                <label className="block text-sm font-medium mb-1">
                  {labels.codeLabel}
                </label>
                <input
                  type="text"
                  value={formCode}
                  onChange={(e) => setFormCode(e.target.value)}
                  className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                  placeholder={`请输入${labels.codeLabel}`}
                  maxLength={20}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  {labels.nameLabel}
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                  placeholder={`请输入${labels.nameLabel}`}
                  maxLength={100}
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formEnabled}
                    onChange={(e) => setFormEnabled(e.target.checked)}
                    className="rounded"
                  />
                  启用
                </label>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={resetForm}
                  className="rounded-md border px-4 py-2 text-sm hover:bg-gray-50 transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={createMut.isPending || updateMut.isPending}
                  className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors disabled:opacity-50"
                >
                  {createMut.isPending || updateMut.isPending
                    ? '保存中...'
                    : '保存'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          加载中...
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-lg border bg-red-50 p-8 text-center">
          <p className="text-red-600 font-medium">加载{labels.label}档案失败</p>
        </div>
      )}

      {/* Table */}
      {data && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                  编码
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                  名称
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-muted-foreground">
                  状态
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                  创建时间
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-12 text-center text-muted-foreground"
                  >
                    暂无{labels.label}档案
                  </td>
                </tr>
              )}
              {data.items.map((item) => (
                <tr
                  key={item.id}
                  className="border-b hover:bg-gray-50/50 transition-colors"
                >
                  <td className="px-4 py-2.5 text-sm font-mono text-xs text-muted-foreground">
                    {item.code}
                  </td>
                  <td className="px-4 py-2.5 text-sm font-medium">
                    {item.name}
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        item.is_enabled
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      {item.is_enabled ? '启用' : '停用'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-sm text-muted-foreground">
                    {new Date(item.created_at).toLocaleDateString('zh-CN')}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => openEdit(item)}
                        className="p-1.5 rounded hover:bg-gray-100 transition-colors"
                        title="编辑"
                      >
                        <Pencil size={14} className="text-muted-foreground" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`确定删除"${item.name}"吗？`)) {
                            deleteMut.mutate(item.id)
                          }
                        }}
                        className="p-1.5 rounded hover:bg-red-50 transition-colors"
                        title="删除"
                      >
                        <Trash2 size={14} className="text-red-500" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          {data.pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50/50">
              <span className="text-sm text-muted-foreground">
                共 {data.total} 条
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1 text-sm rounded border hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  上一页
                </button>
                <span className="px-3 py-1 text-sm text-muted-foreground">
                  {data.page} / {data.pages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                  disabled={page === data.pages}
                  className="px-3 py-1 text-sm rounded border hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
