import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import { Plus, Pencil, Trash2, TrendingDown, Ban } from 'lucide-react'

interface FixedAsset {
  id: string
  code: string
  name: string
  category: string
  purchase_date: string
  purchase_amount: number
  salvage_value: number
  useful_life_months: number
  depreciation_method: string
  monthly_depreciation: number
  accumulated_depreciation: number
  net_value: number
  status: string
  dept_id: string | null
}

interface PaginatedAssets {
  items: FixedAsset[]
  total: number
  page: number
  page_size: number
  pages: number
}

const METHOD_LABELS: Record<string, string> = {
  straight: '直线法',
  double_declining: '双倍余额递减法',
  sum_of_years: '年数总和法',
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  in_use: { label: '使用中', color: 'bg-green-100 text-green-700' },
  disposed: { label: '已处置', color: 'bg-gray-100 text-gray-500' },
  cleared: { label: '已清理', color: 'bg-red-100 text-red-700' },
}

function fmt(n: number): string {
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function AssetList() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [category, setCategory] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<FixedAsset | null>(null)

  // Form fields
  const [formCode, setFormCode] = useState('')
  const [formName, setFormName] = useState('')
  const [formCategory, setFormCategory] = useState('')
  const [formDate, setFormDate] = useState('')
  const [formAmount, setFormAmount] = useState('')
  const [formSalvage, setFormSalvage] = useState('0')
  const [formMonths, setFormMonths] = useState('60')
  const [formMethod, setFormMethod] = useState('straight')
  const [formDept, setFormDept] = useState('')
  const [formError, setFormError] = useState('')

  const { data, isLoading, isError } = useQuery<PaginatedAssets>({
    queryKey: ['fixed-assets', page, status, category],
    queryFn: async () => {
      const params: Record<string, string | number> = { page, page_size: 20 }
      if (status) params.status = status
      if (category) params.category = category
      const { data } = await api.get<PaginatedAssets>('/fixed-assets', { params })
      return data
    },
  })

  const createMut = useMutation({
    mutationFn: (body: unknown) => api.post('/fixed-assets', body),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['fixed-assets'] }); resetForm() },
    onError: (e: unknown) => setFormError((e as {response?:{data?:{detail?:string}}})?.response?.data?.detail || '创建失败'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: unknown }) => api.put(`/fixed-assets/${id}`, body),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['fixed-assets'] }); resetForm() },
    onError: (e: unknown) => setFormError((e as {response?:{data?:{detail?:string}}})?.response?.data?.detail || '更新失败'),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/fixed-assets/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['fixed-assets'] }),
  })

  const depreciateMut = useMutation({
    mutationFn: ({ id, periodId }: { id: string; periodId: string }) =>
      api.post(`/fixed-assets/${id}/depreciate`, { period_id: periodId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['fixed-assets'] }),
  })

  const disposeMut = useMutation({
    mutationFn: ({ id, periodId }: { id: string; periodId: string }) =>
      api.post(`/fixed-assets/${id}/dispose`, { period_id: periodId, disposal_date: new Date().toISOString().slice(0, 10), disposal_amount: 0 }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['fixed-assets'] }),
  })

  function resetForm() { setShowForm(false); setEditing(null); setFormCode(''); setFormName(''); setFormCategory(''); setFormDate(''); setFormAmount(''); setFormSalvage('0'); setFormMonths('60'); setFormMethod('straight'); setFormDept(''); setFormError('') }

  function openCreate() { resetForm(); setShowForm(true) }
  function openEdit(a: FixedAsset) {
    setEditing(a); setFormCode(a.code); setFormName(a.name); setFormCategory(a.category)
    setFormDate(a.purchase_date); setFormAmount(a.purchase_amount.toString())
    setFormSalvage(a.salvage_value.toString()); setFormMonths(a.useful_life_months.toString())
    setFormMethod(a.depreciation_method); setFormDept(a.dept_id || ''); setShowForm(true)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError('')
    const body = {
      code: formCode.trim(), name: formName.trim(), category: formCategory.trim(),
      purchase_date: formDate, purchase_amount: parseFloat(formAmount),
      salvage_value: parseFloat(formSalvage), useful_life_months: parseInt(formMonths),
      depreciation_method: formMethod, dept_id: formDept || null,
    }
    if (editing) updateMut.mutate({ id: editing.id, body })
    else createMut.mutate(body)
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">固定资产</h2>
          <p className="text-sm text-muted-foreground mt-1">管理固定资产卡片、折旧和清理</p>
        </div>
        <button onClick={openCreate} className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90">
          <Plus size={16} />新增资产
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} className="rounded-md border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent">
          <option value="">全部状态</option>
          <option value="in_use">使用中</option>
          <option value="disposed">已处置</option>
          <option value="cleared">已清理</option>
        </select>
        <input type="text" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1) }} className="rounded-md border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent" placeholder="筛选类别..." />
      </div>

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold mb-4">{editing ? '编辑资产' : '新增资产'}</h3>
            <form onSubmit={handleSubmit} className="space-y-3">
              {formError && <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-600">{formError}</div>}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">资产编码</label>
                  <input type="text" value={formCode} onChange={(e) => setFormCode(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent" maxLength={20} required />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">资产名称</label>
                  <input type="text" value={formName} onChange={(e) => setFormName(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent" maxLength={100} required />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">类别</label>
                  <input type="text" value={formCategory} onChange={(e) => setFormCategory(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent" required />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">购置日期</label>
                  <input type="date" value={formDate} onChange={(e) => setFormDate(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent" required />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">原值</label>
                  <input type="number" step="0.01" value={formAmount} onChange={(e) => setFormAmount(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent" required />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">残值</label>
                  <input type="number" step="0.01" value={formSalvage} onChange={(e) => setFormSalvage(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">使用月数</label>
                  <input type="number" value={formMonths} onChange={(e) => setFormMonths(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent" required />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">折旧方法</label>
                  <select value={formMethod} onChange={(e) => setFormMethod(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent">
                    <option value="straight">直线法</option>
                    <option value="double_declining">双倍余额递减法</option>
                    <option value="sum_of_years">年数总和法</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">使用部门ID</label>
                  <input type="text" value={formDept} onChange={(e) => setFormDept(e.target.value)} className="w-full rounded-md border px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent" placeholder="可选" />
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={resetForm} className="rounded-md border px-4 py-2 text-sm hover:bg-gray-50">取消</button>
                <button type="submit" className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90">保存</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isLoading && <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">加载中...</div>}
      {isError && <div className="rounded-lg border bg-red-50 p-8 text-center"><p className="text-red-600 font-medium">加载失败</p></div>}

      {data && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">编码</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">名称</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">类别</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">原值</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">累计折旧</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">净值</th>
                <th className="px-3 py-2.5 text-center text-xs font-medium text-muted-foreground">状态</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">操作</th>
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">暂无固定资产</td></tr>
              )}
              {data.items.map((a) => (
                <tr key={a.id} className="border-b hover:bg-gray-50/50">
                  <td className="px-3 py-2 text-sm font-mono text-xs text-muted-foreground">{a.code}</td>
                  <td className="px-3 py-2 text-sm font-medium">{a.name}</td>
                  <td className="px-3 py-2 text-sm text-muted-foreground">{a.category}</td>
                  <td className="px-3 py-2 text-right text-sm font-mono">{fmt(a.purchase_amount)}</td>
                  <td className="px-3 py-2 text-right text-sm font-mono">{fmt(a.accumulated_depreciation)}</td>
                  <td className="px-3 py-2 text-right text-sm font-mono font-medium">{fmt(a.net_value)}</td>
                  <td className="px-3 py-2 text-center">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_LABELS[a.status]?.color || 'bg-gray-100'}`}>
                      {STATUS_LABELS[a.status]?.label || a.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {a.status === 'in_use' && (
                        <>
                          <button onClick={() => { const pid = prompt('请输入期间ID:'); if (pid) depreciateMut.mutate({ id: a.id, periodId: pid }) }} className="p-1.5 rounded hover:bg-blue-50" title="折旧">
                            <TrendingDown size={14} className="text-blue-500" />
                          </button>
                          <button onClick={() => { const pid = prompt('请输入期间ID:'); if (pid && confirm(`确定清理"${a.name}"吗？`)) disposeMut.mutate({ id: a.id, periodId: pid }) }} className="p-1.5 rounded hover:bg-red-50" title="清理">
                            <Ban size={14} className="text-red-500" />
                          </button>
                        </>
                      )}
                      <button onClick={() => openEdit(a)} className="p-1.5 rounded hover:bg-gray-100" title="编辑">
                        <Pencil size={14} className="text-muted-foreground" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50/50">
              <span className="text-sm text-muted-foreground">共 {data.total} 项</span>
              <div className="flex items-center gap-1">
                <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1 text-sm rounded border hover:bg-gray-100 disabled:opacity-50">上一页</button>
                <span className="px-3 py-1 text-sm text-muted-foreground">{data.page} / {data.pages}</span>
                <button onClick={() => setPage((p) => Math.min(data.pages, p + 1))} disabled={page === data.pages} className="px-3 py-1 text-sm rounded border hover:bg-gray-100 disabled:opacity-50">下一页</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
