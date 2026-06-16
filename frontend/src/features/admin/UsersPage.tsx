import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type { User, CreateUserRequest, UpdateUserRequest, RoleInfo } from '@/types/user'
import { DataTable, type ColumnDef } from '@/components/DataTable/DataTable'
import { DataTablePagination } from '@/components/DataTable/DataTablePagination'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { StatusBadge } from '@/components/StatusBadge'
import { Plus, Pencil, Trash2, Search, X } from 'lucide-react'

interface UserForm {
  username: string
  password: string
  display_name: string
  role_id: string
  is_enabled: boolean
}

const emptyForm: UserForm = {
  username: '',
  password: '',
  display_name: '',
  role_id: '',
  is_enabled: true,
}

export default function UsersPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'enabled' | 'disabled'>('all')
  const [showForm, setShowForm] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [form, setForm] = useState<UserForm>(emptyForm)
  const [deleteUser, setDeleteUser] = useState<User | null>(null)
  const [formError, setFormError] = useState('')

  // Fetch users
  const { data: usersData, isLoading } = useQuery({
    queryKey: ['users', page, pageSize, statusFilter],
    queryFn: async () => {
      const params: Record<string, string | number> = {
        page,
        page_size: pageSize,
      }
      if (statusFilter === 'enabled') params.is_enabled = 'true'
      if (statusFilter === 'disabled') params.is_enabled = 'false'

      const { data } = await api.get('/admin/users', { params })
      return data
    },
  })

  // Fetch roles for dropdown
  const { data: roles } = useQuery<RoleInfo[]>({
    queryKey: ['roles'],
    queryFn: async () => {
      const { data } = await api.get('/admin/roles')
      return data
    },
  })

  // Create user mutation
  const createMutation = useMutation({
    mutationFn: async (payload: CreateUserRequest) => {
      const { data } = await api.post('/admin/users', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      handleCloseForm()
    },
    onError: (error: any) => {
      setFormError(error.response?.data?.detail || '创建用户失败')
    },
  })

  // Update user mutation
  const updateMutation = useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: UpdateUserRequest }) => {
      const { data } = await api.put(`/admin/users/${id}`, payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      handleCloseForm()
    },
    onError: (error: any) => {
      setFormError(error.response?.data?.detail || '更新用户失败')
    },
  })

  // Delete user mutation
  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/admin/users/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setDeleteUser(null)
    },
  })

  const handleOpenForm = (user?: User) => {
    if (user) {
      setEditingUser(user)
      setForm({
        username: user.username,
        password: '',
        display_name: user.display_name,
        role_id: user.role_id,
        is_enabled: user.is_enabled,
      })
    } else {
      setEditingUser(null)
      setForm(emptyForm)
    }
    setFormError('')
    setShowForm(true)
  }

  const handleCloseForm = () => {
    setShowForm(false)
    setEditingUser(null)
    setForm(emptyForm)
    setFormError('')
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')

    if (!form.username.trim() || !form.display_name.trim() || !form.role_id) {
      setFormError('请填写必填字段')
      return
    }

    if (editingUser) {
      const payload: UpdateUserRequest = {
        display_name: form.display_name,
        role_id: form.role_id,
        is_enabled: form.is_enabled,
      }
      if (form.password) {
        payload.password = form.password
      }
      updateMutation.mutate({ id: editingUser.id, payload })
    } else {
      if (!form.password) {
        setFormError('请设置密码')
        return
      }
      const payload: CreateUserRequest = {
        username: form.username,
        password: form.password,
        display_name: form.display_name,
        role_id: form.role_id,
      }
      createMutation.mutate(payload)
    }
  }

  const handleDelete = () => {
    if (deleteUser) {
      deleteMutation.mutate(deleteUser.id)
    }
  }

  const getRoleName = (roleId: string) => {
    return roles?.find((r) => r.id === roleId)?.name || '-'
  }

  // Filter by search term
  const filteredData = usersData?.items?.filter((user: User) => {
    if (!search) return true
    const term = search.toLowerCase()
    return (
      user.username.toLowerCase().includes(term) ||
      user.display_name.toLowerCase().includes(term)
    )
  }) || []

  const columns: ColumnDef<User>[] = [
    {
      key: 'username',
      header: '用户名',
      accessorKey: 'username',
      sortable: true,
    },
    {
      key: 'display_name',
      header: '显示名称',
      accessorKey: 'display_name',
      sortable: true,
    },
    {
      key: 'role',
      header: '角色',
      cell: (user) => (
        <span className="text-sm">{getRoleName(user.role_id)}</span>
      ),
    },
    {
      key: 'status',
      header: '状态',
      cell: (user) => (
        <StatusBadge
          status={user.is_enabled ? 'enabled' : 'disabled'}
          label={user.is_enabled ? '启用' : '禁用'}
        />
      ),
    },
    {
      key: 'last_login',
      header: '最后登录',
      cell: (user) => (
        <span className="text-sm text-muted-foreground">
          {user.last_login_at
            ? new Date(user.last_login_at).toLocaleString('zh-CN')
            : '-'}
        </span>
      ),
    },
    {
      key: 'created_at',
      header: '创建时间',
      cell: (user) => (
        <span className="text-sm text-muted-foreground">
          {new Date(user.created_at).toLocaleString('zh-CN')}
        </span>
      ),
    },
  ]

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">用户管理</h1>
        <button
          onClick={() => handleOpenForm()}
          className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors"
        >
          <Plus size={16} />
          添加用户
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-4 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索用户名或显示名称..."
            className="w-full rounded-md border bg-card pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as any)
            setPage(1)
          }}
          className="rounded-md border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
        >
          <option value="all">全部状态</option>
          <option value="enabled">已启用</option>
          <option value="disabled">已禁用</option>
        </select>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={filteredData}
        total={usersData?.total || 0}
        page={page}
        pageSize={pageSize}
        onPaginationChange={(newPage, newPageSize) => {
          setPage(newPage)
          setPageSize(newPageSize)
        }}
        isLoading={isLoading}
        rowActions={(user) => (
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleOpenForm(user)}
              className="p-1.5 rounded hover:bg-gray-100 text-muted-foreground hover:text-foreground transition-colors"
              title="编辑"
            >
              <Pencil size={16} />
            </button>
            <button
              onClick={() => setDeleteUser(user)}
              className="p-1.5 rounded hover:bg-red-50 text-muted-foreground hover:text-red-600 transition-colors"
              title="删除"
            >
              <Trash2 size={16} />
            </button>
          </div>
        )}
        emptyMessage="暂无用户数据"
      />

      <DataTablePagination
        page={page}
        pageSize={pageSize}
        total={usersData?.total || 0}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size)
          setPage(1)
        }}
      />

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={handleCloseForm} />
          <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">
                {editingUser ? '编辑用户' : '添加用户'}
              </h3>
              <button
                onClick={handleCloseForm}
                className="p-1 rounded hover:bg-gray-100 text-muted-foreground"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  用户名 {editingUser ? '(不可修改)' : '*'}
                </label>
                <input
                  type="text"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  disabled={!!editingUser}
                  className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent disabled:bg-gray-100 disabled:cursor-not-allowed"
                  placeholder="请输入用户名"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  密码 {editingUser ? '(留空则不修改)' : '*'}
                </label>
                <input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                  placeholder={editingUser ? '留空保持不变' : '请输入密码'}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">显示名称 *</label>
                <input
                  type="text"
                  value={form.display_name}
                  onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                  className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                  placeholder="请输入显示名称"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">角色 *</label>
                <select
                  value={form.role_id}
                  onChange={(e) => setForm({ ...form, role_id: e.target.value })}
                  className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                >
                  <option value="">请选择角色</option>
                  {roles?.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_enabled"
                  checked={form.is_enabled}
                  onChange={(e) => setForm({ ...form, is_enabled: e.target.checked })}
                  className="rounded border-gray-300"
                />
                <label htmlFor="is_enabled" className="text-sm">
                  启用账户
                </label>
              </div>

              {formError && (
                <div className="text-sm text-destructive bg-red-50 border border-red-200 rounded px-3 py-2">
                  {formError}
                </div>
              )}

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
                  {createMutation.isPending || updateMutation.isPending
                    ? '保存中...'
                    : '保存'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deleteUser}
        title="删除用户"
        message={`确定要删除用户 "${deleteUser?.display_name}" 吗？此操作将禁用该用户的账户。`}
        confirmLabel="删除"
        cancelLabel="取消"
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setDeleteUser(null)}
      />
    </div>
  )
}
