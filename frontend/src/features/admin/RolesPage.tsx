import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type { RoleInfo } from '@/types/user'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Plus, X } from 'lucide-react'
import { Permissions, type Permission } from '@/lib/constants'

interface RoleForm {
  name: string
  permissions: Record<string, boolean>
}

const emptyForm: RoleForm = {
  name: '',
  permissions: {},
}

export default function RolesPage() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<RoleForm>(emptyForm)
  const [formError, setFormError] = useState('')

  // Fetch roles
  const { data: roles, isLoading } = useQuery<RoleInfo[]>({
    queryKey: ['roles'],
    queryFn: async () => {
      const { data } = await api.get('/admin/roles')
      return data
    },
  })

  // Create role mutation
  const createMutation = useMutation({
    mutationFn: async (payload: { name: string; permissions: Record<string, boolean> }) => {
      const { data } = await api.post('/admin/roles', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      handleCloseForm()
    },
    onError: (error: any) => {
      setFormError(error.response?.data?.detail || '创建角色失败')
    },
  })

  const handleOpenForm = () => {
    setForm(emptyForm)
    setFormError('')
    setShowForm(true)
  }

  const handleCloseForm = () => {
    setShowForm(false)
    setForm(emptyForm)
    setFormError('')
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')

    if (!form.name.trim()) {
      setFormError('请输入角色名称')
      return
    }

    createMutation.mutate({
      name: form.name,
      permissions: form.permissions,
    })
  }

  const togglePermission = (perm: Permission) => {
    setForm({
      ...form,
      permissions: {
        ...form.permissions,
        [perm]: !form.permissions[perm],
      },
    })
  }

  const selectAll = () => {
    const allPerms: Record<string, boolean> = {}
    Permissions.forEach((p) => { allPerms[p] = true })
    setForm({ ...form, permissions: allPerms })
  }

  const clearAll = () => {
    setForm({ ...form, permissions: {} })
  }

  const getPermLabel = (perm: string) => {
    const labels: Record<string, string> = {
      'voucher:create': '创建凭证',
      'voucher:edit:own': '编辑自己的凭证',
      'voucher:edit:any': '编辑所有凭证',
      'voucher:delete:draft': '删除草稿凭证',
      'voucher:audit': '审核凭证',
      'voucher:unaudit': '取消审核',
      'voucher:post': '记账',
      'voucher:reverse': '冲销',
      'account:read': '查看科目',
      'account:manage': '管理科目',
      'ledger:read': '查看账簿',
      'report:read': '查看报表',
      'report:export': '导出报表',
      'period:close': '结账',
      'period:reopen': '反结账',
      'aux:manage': '管理辅助核算',
      'cashier:use': '出纳操作',
      'assets:manage': '管理固定资产',
      'ai:use': 'AI 功能',
      'admin:users': '管理用户',
      'admin:roles': '管理角色',
      'admin:backup': '数据备份',
      'admin:audit-log': '审计日志',
    }
    return labels[perm] || perm
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">角色管理</h1>
        <button
          onClick={handleOpenForm}
          className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors"
        >
          <Plus size={16} />
          添加角色
        </button>
      </div>

      {/* Roles List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : roles && roles.length > 0 ? (
        <div className="grid gap-4">
          {roles.map((role) => (
            <div
              key={role.id}
              className="rounded-lg border bg-card p-6"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold">{role.name}</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    {Object.keys(role.permissions || {}).length} 个权限
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {role.permissions && Object.keys(role.permissions).length > 0 ? (
                  Object.keys(role.permissions).map((perm) => (
                    <span
                      key={perm}
                      className="inline-flex items-center rounded-full border border-accent/30 bg-accent/5 px-2.5 py-0.5 text-xs font-medium text-accent"
                    >
                      {getPermLabel(perm)}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground">无权限</span>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          <p>暂无角色数据</p>
        </div>
      )}

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={handleCloseForm} />
          <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">添加角色</h3>
              <button
                onClick={handleCloseForm}
                className="p-1 rounded hover:bg-gray-100 text-muted-foreground"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">角色名称 *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                  placeholder="请输入角色名称"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium">权限配置</label>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={selectAll}
                      className="text-xs text-accent hover:underline"
                    >
                      全选
                    </button>
                    <span className="text-muted-foreground">|</span>
                    <button
                      type="button"
                      onClick={clearAll}
                      className="text-xs text-accent hover:underline"
                    >
                      清空
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 p-4 border rounded-lg">
                  {Permissions.map((perm) => (
                    <label
                      key={perm}
                      className="flex items-center gap-2 text-sm cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={!!form.permissions[perm]}
                        onChange={() => togglePermission(perm)}
                        className="rounded border-gray-300"
                      />
                      {getPermLabel(perm)}
                    </label>
                  ))}
                </div>
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
                  disabled={createMutation.isPending}
                  className="px-4 py-2 text-sm font-medium rounded-md bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50"
                >
                  {createMutation.isPending ? '保存中...' : '保存'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
