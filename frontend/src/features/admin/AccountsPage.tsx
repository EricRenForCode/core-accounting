import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type { Account, AccountTreeNode, CreateAccountRequest, UpdateAccountRequest } from '@/types/account'
import { AccountTypeLabels, AccountType, AuxType } from '@/lib/constants'
import type { AccountTypeValue, DCTypeValue, AuxTypeValue } from '@/lib/constants'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { StatusBadge } from '@/components/StatusBadge'
import { AccountPicker } from '@/components/AccountPicker'
import { Plus, Pencil, Trash2, Search, X, ChevronRight, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

// ─── Constants ───────────────────────────────────────

const TYPE_FILTERS: Array<{ value: AccountTypeValue | 'all'; label: string }> = [
  { value: 'all', label: '全部' },
  { value: AccountType.ASSET, label: '资产' },
  { value: AccountType.LIABILITY, label: '负债' },
  { value: AccountType.EQUITY, label: '权益' },
  { value: AccountType.REVENUE, label: '收入' },
  { value: AccountType.EXPENSE, label: '费用' },
]

const AUX_OPTIONS: Array<{ value: AuxTypeValue; label: string }> = [
  { value: AuxType.DEPARTMENT, label: '部门' },
  { value: AuxType.INDIVIDUAL, label: '个人' },
  { value: AuxType.COUNTERPARTY, label: '单位' },
  { value: AuxType.PROJECT, label: '项目' },
]

// ─── Form State ──────────────────────────────────────

interface AccountForm {
  parent_id: string
  code: string
  name: string
  type: AccountTypeValue
  dc_type: DCTypeValue
  is_cash: boolean
  aux_types: AuxTypeValue[]
  is_quantity: boolean
  quantity_unit: string
}

const emptyForm: AccountForm = {
  parent_id: '',
  code: '',
  name: '',
  type: AccountType.ASSET,
  dc_type: 'D',
  is_cash: false,
  aux_types: [],
  is_quantity: false,
  quantity_unit: '',
}

// ─── Helpers ─────────────────────────────────────────

function flattenTree(
  nodes: AccountTreeNode[],
  expandedIds: Set<string>,
): AccountTreeNode[] {
  const result: AccountTreeNode[] = []
  const walk = (items: AccountTreeNode[]) => {
    for (const node of items) {
      result.push(node)
      if (node.children.length > 0 && expandedIds.has(node.id)) {
        walk(node.children)
      }
    }
  }
  walk(nodes)
  return result
}

// ─── Component ───────────────────────────────────────

export default function AccountsPage() {
  const queryClient = useQueryClient()

  // Filter state
  const [typeFilter, setTypeFilter] = useState<AccountTypeValue | 'all'>('all')
  const [search, setSearch] = useState('')
  const [showDisabled, setShowDisabled] = useState(false)

  // Tree expand/collapse
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  // Form state
  const [showForm, setShowForm] = useState(false)
  const [editingAccount, setEditingAccount] = useState<Account | null>(null)
  const [form, setForm] = useState<AccountForm>(emptyForm)
  const [formError, setFormError] = useState('')

  // Inline editing
  const [inlineEditId, setInlineEditId] = useState<string | null>(null)
  const [inlineEditName, setInlineEditName] = useState('')

  // Delete state
  const [deleteTarget, setDeleteTarget] = useState<Account | null>(null)

  // ─── Data Fetching ──────────────────────────────────

  // Flat list (for search/filter convenience)
  const { data: accountsData } = useQuery({
    queryKey: ['accounts', 'flat', typeFilter, showDisabled],
    queryFn: async () => {
      const params: Record<string, string | number> = {
        page: 1,
        page_size: 500,
      }
      if (typeFilter !== 'all') params.type = typeFilter
      if (!showDisabled) params.is_enabled = 'true'

      const { data } = await api.get('/accounts', { params })
      return data
    },
  })

  // Tree (for hierarchical display)
  const { data: tree = [], isLoading } = useQuery<AccountTreeNode[]>({
    queryKey: ['accounts', 'tree', showDisabled],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (!showDisabled) params.is_enabled = 'true'
      const { data } = await api.get('/accounts/tree', { params })
      // Backend returns AccountTreeResponse { accounts, total_count }; the table needs the array.
      return data.accounts ?? []
    },
  })

  // ─── Mutations ─────────────────────────────────────

  const createMutation = useMutation({
    mutationFn: async (payload: CreateAccountRequest) => {
      const { data } = await api.post('/accounts', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      handleCloseForm()
    },
    onError: (error: any) => {
      setFormError(error.response?.data?.detail || '创建科目失败')
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: UpdateAccountRequest }) => {
      const { data } = await api.put(`/accounts/${id}`, payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      handleCloseForm()
      setInlineEditId(null)
    },
    onError: (error: any) => {
      setFormError(error.response?.data?.detail || '更新科目失败')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/accounts/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      setDeleteTarget(null)
    },
    onError: (error: any) => {
      const detail = error.response?.data?.detail || '删除科目失败'
      alert(detail)
      setDeleteTarget(null)
    },
  })

  // ─── Form Handlers ──────────────────────────────────

  const handleOpenForm = (account?: Account) => {
    if (account) {
      setEditingAccount(account)
      setForm({
        parent_id: account.parent_id || '',
        code: account.code,
        name: account.name,
        type: account.type,
        dc_type: account.dc_type,
        is_cash: account.is_cash,
        aux_types: account.aux_types || [],
        is_quantity: account.is_quantity,
        quantity_unit: account.quantity_unit || '',
      })
    } else {
      setEditingAccount(null)
      setForm(emptyForm)
    }
    setFormError('')
    setShowForm(true)
  }

  const handleCloseForm = () => {
    setShowForm(false)
    setEditingAccount(null)
    setForm(emptyForm)
    setFormError('')
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')

    if (!form.code.trim() || !form.name.trim()) {
      setFormError('请填写科目编码和科目名称')
      return
    }

    // Compute level: 1 for root, parent.level + 1 for children
    const parentLevel = form.parent_id
      ? accountsData?.accounts?.find((a) => a.id === form.parent_id)?.level
      : null
    const level = parentLevel != null ? parentLevel + 1 : 1

    const payload: CreateAccountRequest = {
      code: form.code.trim(),
      name: form.name.trim(),
      level,
      type: form.type,
      dc_type: form.dc_type,
      is_cash: form.is_cash,
      aux_types: form.aux_types.length > 0 ? form.aux_types : undefined,
      is_quantity: form.is_quantity,
      quantity_unit: form.is_quantity ? form.quantity_unit.trim() : undefined,
    }

    if (form.parent_id) {
      payload.parent_id = form.parent_id
    }

    if (editingAccount) {
      updateMutation.mutate({ id: editingAccount.id, payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const handleDelete = () => {
    if (deleteTarget) {
      deleteMutation.mutate(deleteTarget.id)
    }
  }

  // ─── Toggle enable/disable ──────────────────────────

  const handleToggleEnabled = (account: Account) => {
    updateMutation.mutate({
      id: account.id,
      payload: { is_enabled: !account.is_enabled },
    })
  }

  // ─── Inline edit name ───────────────────────────────

  const startInlineEdit = (account: Account) => {
    setInlineEditId(account.id)
    setInlineEditName(account.name)
  }

  const saveInlineEdit = (account: Account) => {
    if (inlineEditName.trim() && inlineEditName.trim() !== account.name) {
      updateMutation.mutate({
        id: account.id,
        payload: { name: inlineEditName.trim() },
      })
    } else {
      setInlineEditId(null)
    }
  }

  const cancelInlineEdit = () => {
    setInlineEditId(null)
    setInlineEditName('')
  }

  // ─── Tree state ─────────────────────────────────────

  // Filter tree by type if a type filter is active
  const filteredTree = useMemo(() => {
    if (typeFilter === 'all') return tree
    const filterNodes = (nodes: AccountTreeNode[]): AccountTreeNode[] => {
      return nodes
        .filter((n) => n.type === typeFilter || n.children.some(() => true))
        .map((n) => ({ ...n, children: filterNodes(n.children) }))
        .filter((n) => n.type === typeFilter || n.children.length > 0)
    }
    return filterNodes(tree)
  }, [tree, typeFilter])

  // Search filter across the flattened visible tree
  const flattenAll = useMemo(() => {
    // Expand all for search purposes
    const allIds = new Set<string>()
    const collect = (nodes: AccountTreeNode[]) => {
      for (const n of nodes) {
        allIds.add(n.id)
        if (n.children.length > 0) collect(n.children)
      }
    }
    collect(filteredTree)
    return allIds
  }, [filteredTree])

  const visibleItems = useMemo(() => {
    const flat = flattenTree(filteredTree, search ? flattenAll : expandedIds)
    if (!search) return flat
    const term = search.toLowerCase()
    return flat.filter(
      (n) =>
        n.code.toLowerCase().includes(term) ||
        n.name.toLowerCase().includes(term) ||
        n.code.replace(/-/g, '').includes(term.replace(/-/g, '')),
    )
  }, [filteredTree, expandedIds, search, flattenAll])

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const expandAll = () => {
    const allIds = new Set<string>()
    const collect = (nodes: AccountTreeNode[]) => {
      for (const n of nodes) {
        if (n.children.length > 0) allIds.add(n.id)
        collect(n.children)
      }
    }
    collect(filteredTree)
    setExpandedIds(allIds)
  }

  const collapseAll = () => {
    setExpandedIds(new Set())
  }

  // ─── Type badge colors ──────────────────────────────

  const typeColors: Record<AccountTypeValue, string> = {
    asset: 'bg-blue-100 text-blue-700 border-blue-300',
    liability: 'bg-orange-100 text-orange-700 border-orange-300',
    equity: 'bg-purple-100 text-purple-700 border-purple-300',
    revenue: 'bg-green-100 text-green-700 border-green-300',
    expense: 'bg-red-100 text-red-700 border-red-300',
  }

  // ─── Render ─────────────────────────────────────────

  const hasChildren = (node: AccountTreeNode) => node.children.length > 0
  const isExpanded = (node: AccountTreeNode) => expandedIds.has(node.id)

  return (
    <div className="p-6">
      {/* ── Header ─────────────────────────────────── */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="text-2xl font-bold">科目管理</h1>
          <p className="text-sm text-muted-foreground mt-1">会计科目基础数据维护</p>
        </div>
        <button
          onClick={() => handleOpenForm()}
          className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors"
        >
          <Plus size={16} />
          新增科目
        </button>
      </div>

      {/* ── Filter Bar ─────────────────────────────── */}
      <div className="space-y-3 mb-4">
        {/* Type tabs */}
        <div className="flex items-center gap-1 flex-wrap">
          {TYPE_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setTypeFilter(f.value)}
              className={cn(
                'px-3 py-1.5 text-sm rounded-md transition-colors',
                typeFilter === f.value
                  ? 'bg-accent text-white'
                  : 'bg-gray-100 text-muted-foreground hover:bg-gray-200',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Search + toggles */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索科目编码或名称..."
              className="w-full rounded-md border bg-card pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>

          <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showDisabled}
              onChange={(e) => setShowDisabled(e.target.checked)}
              className="rounded border-gray-300"
            />
            显示已禁用
          </label>

          <div className="flex items-center gap-1">
            <button
              onClick={expandAll}
              className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-gray-100 rounded transition-colors"
            >
              全部展开
            </button>
            <button
              onClick={collapseAll}
              className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-gray-100 rounded transition-colors"
            >
              全部收起
            </button>
          </div>
        </div>
      </div>

      {/* ── Tree Table ─────────────────────────────── */}
      <div className="rounded-lg border bg-card">
        {isLoading ? (
          <div className="p-8 space-y-3">
            {Array.from({ length: 8 }, (_, i) => (
              <div
                key={i}
                className="h-8 bg-gray-100 rounded animate-pulse"
                style={{ animationDelay: `${i * 80}ms` }}
              />
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="w-10 px-3 py-3" />
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    科目编码
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    科目名称
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    类型
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider w-20">
                    余额方向
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider w-20">
                    现金科目
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    辅助核算
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider w-20">
                    状态
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider w-28">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody>
                {visibleItems.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-16 text-center text-muted-foreground">
                      暂无科目数据
                    </td>
                  </tr>
                ) : (
                  visibleItems.map((node) => {
                    const isEditing = inlineEditId === node.id
                    const expandable = hasChildren(node)
                    const expanded = isExpanded(node)
                    const indent = node.level * 24

                    return (
                      <tr
                        key={node.id}
                        className={cn(
                          'border-b last:border-b-0 hover:bg-gray-50 transition-colors',
                          !node.is_enabled && 'opacity-50',
                        )}
                      >
                        {/* Expand/Collapse */}
                        <td className="px-3 py-3">
                          {expandable ? (
                            <button
                              onClick={() => toggleExpand(node.id)}
                              className="p-0.5 rounded hover:bg-gray-200 transition-colors"
                            >
                              {expanded ? (
                                <ChevronDown size={16} className="text-muted-foreground" />
                              ) : (
                                <ChevronRight size={16} className="text-muted-foreground" />
                              )}
                            </button>
                          ) : null}
                        </td>

                        {/* Code */}
                        <td className="px-4 py-3">
                          <span
                            className="font-mono text-sm"
                            style={{ paddingLeft: `${indent}px` }}
                          >
                            {node.code}
                          </span>
                        </td>

                        {/* Name */}
                        <td className="px-4 py-3">
                          {isEditing ? (
                            <div className="flex items-center gap-1">
                              <input
                                type="text"
                                value={inlineEditName}
                                onChange={(e) => setInlineEditName(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') saveInlineEdit(node)
                                  if (e.key === 'Escape') cancelInlineEdit()
                                }}
                                className="rounded border px-2 py-1 text-sm w-full focus:outline-none focus:ring-1 focus:ring-accent"
                                autoFocus
                              />
                              <button
                                onClick={() => saveInlineEdit(node)}
                                className="p-1 text-green-600 hover:bg-green-50 rounded"
                              >
                                ✓
                              </button>
                              <button
                                onClick={cancelInlineEdit}
                                className="p-1 text-muted-foreground hover:bg-gray-100 rounded"
                              >
                                <X size={14} />
                              </button>
                            </div>
                          ) : (
                            <span
                              className="text-sm font-medium"
                              style={{ paddingLeft: `${indent}px` }}
                            >
                              {node.name}
                            </span>
                          )}
                        </td>

                        {/* Type */}
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium',
                              typeColors[node.type] || 'bg-gray-100 text-gray-700 border-gray-300',
                            )}
                          >
                            {AccountTypeLabels[node.type]}
                          </span>
                        </td>

                        {/* DC Type */}
                        <td className="px-4 py-3 text-center">
                          <span
                            className={cn(
                              'inline-flex items-center justify-center w-8 h-6 rounded text-xs font-bold',
                              node.dc_type === 'D'
                                ? 'bg-blue-50 text-blue-600'
                                : 'bg-orange-50 text-orange-600',
                            )}
                          >
                            {node.dc_type === 'D' ? '借' : '贷'}
                          </span>
                        </td>

                        {/* Is Cash */}
                        <td className="px-4 py-3 text-center">
                          {node.is_cash ? (
                            <span className="text-green-600 text-xs font-medium">是</span>
                          ) : (
                            <span className="text-muted-foreground text-xs">—</span>
                          )}
                        </td>

                        {/* Aux Types */}
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-1">
                            {node.aux_types && node.aux_types.length > 0 ? (
                              node.aux_types.map((aux) => (
                                <span
                                  key={aux}
                                  className="inline-flex items-center rounded bg-gray-100 px-1.5 py-0.5 text-xs text-muted-foreground"
                                >
                                  {aux}
                                </span>
                              ))
                            ) : (
                              <span className="text-muted-foreground text-xs">—</span>
                            )}
                          </div>
                        </td>

                        {/* Status */}
                        <td className="px-4 py-3 text-center">
                          <StatusBadge
                            status={node.is_enabled ? 'open' : 'closed'}
                            label={node.is_enabled ? '启用' : '禁用'}
                          />
                        </td>

                        {/* Actions */}
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            {/* Toggle enabled */}
                            <button
                              onClick={() => handleToggleEnabled(node)}
                              title={node.is_enabled ? '禁用' : '启用'}
                              className={cn(
                                'px-2 py-1 text-xs rounded transition-colors',
                                node.is_enabled
                                  ? 'text-orange-600 hover:bg-orange-50'
                                  : 'text-green-600 hover:bg-green-50',
                              )}
                            >
                              {node.is_enabled ? '禁用' : '启用'}
                            </button>

                            {/* Edit name inline */}
                            <button
                              onClick={() => startInlineEdit(node)}
                              className="p-1.5 rounded hover:bg-gray-100 text-muted-foreground hover:text-foreground transition-colors"
                              title="编辑名称"
                            >
                              <Pencil size={14} />
                            </button>

                            {/* Edit full form */}
                            <button
                              onClick={() => handleOpenForm(node)}
                              className="p-1 rounded hover:bg-blue-50 text-muted-foreground hover:text-blue-600 transition-colors text-xs"
                              title="编辑科目"
                            >
                              编辑
                            </button>

                            {/* Delete */}
                            <button
                              onClick={() => setDeleteTarget(node)}
                              className="p-1.5 rounded hover:bg-red-50 text-muted-foreground hover:text-red-600 transition-colors"
                              title="删除"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Quick stats ─────────────────────────────── */}
      <div className="mt-4 flex items-center gap-4 text-sm text-muted-foreground">
        <span>
          共{' '}
          <span className="font-medium text-foreground">
            {accountsData?.total ?? visibleItems.length}
          </span>{' '}
          个科目
        </span>
        {search && (
          <span>
            筛选结果 <span className="font-medium text-foreground">{visibleItems.length}</span> 条
          </span>
        )}
      </div>

      {/* ── Create/Edit Modal ─────────────────────────── */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={handleCloseForm} />
          <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">
                {editingAccount ? '编辑科目' : '新增科目'}
              </h3>
              <button
                onClick={handleCloseForm}
                className="p-1 rounded hover:bg-gray-100 text-muted-foreground"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Parent account */}
              <div>
                <label className="block text-sm font-medium mb-1">上级科目</label>
                <AccountPicker
                  value={form.parent_id || undefined}
                  onChange={(acc) => setForm({ ...form, parent_id: acc.id })}
                  excludeIds={editingAccount ? [editingAccount.id] : undefined}
                  filter={(node) => node.level < 3}
                  placeholder="无（一级科目）"
                />
              </div>

              {/* Code */}
              <div>
                <label className="block text-sm font-medium mb-1">
                  科目编码 <span className="text-destructive">*</span>
                </label>
                <input
                  type="text"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  className="w-full rounded-md border px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent"
                  placeholder="例如：1001"
                />
              </div>

              {/* Name */}
              <div>
                <label className="block text-sm font-medium mb-1">
                  科目名称 <span className="text-destructive">*</span>
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                  placeholder="例如：库存现金"
                />
              </div>

              {/* Type */}
              <div>
                <label className="block text-sm font-medium mb-1">
                  科目类型 <span className="text-destructive">*</span>
                </label>
                <select
                  value={form.type}
                  onChange={(e) => setForm({ ...form, type: e.target.value as AccountTypeValue })}
                  className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                >
                  {TYPE_FILTERS.filter((f) => f.value !== 'all').map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* DC Type */}
              <div>
                <label className="block text-sm font-medium mb-1">
                  余额方向 <span className="text-destructive">*</span>
                </label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="dc_type"
                      value="D"
                      checked={form.dc_type === 'D'}
                      onChange={() => setForm({ ...form, dc_type: 'D' })}
                      className="text-accent"
                    />
                    <span className="text-sm">借 (D)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="dc_type"
                      value="C"
                      checked={form.dc_type === 'C'}
                      onChange={() => setForm({ ...form, dc_type: 'C' })}
                      className="text-accent"
                    />
                    <span className="text-sm">贷 (C)</span>
                  </label>
                </div>
              </div>

              {/* Is Cash */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_cash"
                  checked={form.is_cash}
                  onChange={(e) => setForm({ ...form, is_cash: e.target.checked })}
                  className="rounded border-gray-300"
                />
                <label htmlFor="is_cash" className="text-sm">
                  是否现金科目
                </label>
              </div>

              {/* Aux Types */}
              <div>
                <label className="block text-sm font-medium mb-2">辅助核算类型</label>
                <div className="flex flex-wrap gap-3">
                  {AUX_OPTIONS.map((opt) => (
                    <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.aux_types.includes(opt.value)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setForm({ ...form, aux_types: [...form.aux_types, opt.value] })
                          } else {
                            setForm({
                              ...form,
                              aux_types: form.aux_types.filter((a) => a !== opt.value),
                            })
                          }
                        }}
                        className="rounded border-gray-300"
                      />
                      <span className="text-sm">{opt.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Is Quantity */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_quantity"
                  checked={form.is_quantity}
                  onChange={(e) => setForm({ ...form, is_quantity: e.target.checked })}
                  className="rounded border-gray-300"
                />
                <label htmlFor="is_quantity" className="text-sm">
                  数量核算
                </label>
              </div>

              {/* Quantity Unit (conditional) */}
              {form.is_quantity && (
                <div>
                  <label className="block text-sm font-medium mb-1">
                    计量单位 <span className="text-destructive">*</span>
                  </label>
                  <input
                    type="text"
                    value={form.quantity_unit}
                    onChange={(e) => setForm({ ...form, quantity_unit: e.target.value })}
                    className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                    placeholder="例如：个、公斤、米"
                  />
                </div>
              )}

              {/* Form error */}
              {formError && (
                <div className="text-sm text-destructive bg-red-50 border border-red-200 rounded px-3 py-2">
                  {formError}
                </div>
              )}

              {/* Submit */}
              <div className="flex justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={handleCloseForm}
                  className="px-4 py-2 text-sm font-medium rounded-md border border-border hover:bg-gray-50 transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="px-4 py-2 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50"
                >
                  {createMutation.isPending || updateMutation.isPending ? '保存中...' : '保存'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Delete Confirmation ───────────────────────── */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="删除科目"
        message={`确定要删除科目 "${deleteTarget?.code} ${deleteTarget?.name}" 吗？${
          (deleteTarget as AccountTreeNode)?.children?.length
            ? ' 该科目包含子科目，无法删除。'
            : ' 此操作不可撤销。'
        }`}
        confirmLabel="删除"
        cancelLabel="取消"
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
