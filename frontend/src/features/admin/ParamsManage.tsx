import { useEffect, useState } from 'react'
import api from '@/lib/api'

interface SystemParams {
  params: Record<string, string>
}

const FIELD_CONFIG: Record<string, { label: string; type: 'text' | 'select'; options?: { value: string; label: string }[] }> = {
  company_name: {
    label: '公司名称',
    type: 'text',
  },
  base_currency: {
    label: '本位币',
    type: 'select',
    options: [
      { value: 'CNY', label: '人民币 (CNY)' },
      { value: 'USD', label: '美元 (USD)' },
      { value: 'EUR', label: '欧元 (EUR)' },
      { value: 'JPY', label: '日元 (JPY)' },
    ],
  },
  accounting_standard: {
    label: '会计制度',
    type: 'select',
    options: [
      { value: '企业会计准则', label: '企业会计准则' },
      { value: '小企业会计准则', label: '小企业会计准则' },
    ],
  },
  voucher_no_prefix: {
    label: '凭证号前缀',
    type: 'text',
  },
  default_depreciation_method: {
    label: '折旧方法默认值',
    type: 'select',
    options: [
      { value: 'straight', label: '直线法 (straight)' },
      { value: 'double_declining', label: '双倍余额递减法 (double_declining)' },
      { value: 'sum_of_years', label: '年数总和法 (sum_of_years)' },
    ],
  },
}

export default function ParamsManage() {
  const [params, setParams] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    loadParams()
  }, [])

  async function loadParams() {
    setLoading(true)
    setError('')
    try {
      const { data } = await api.get<SystemParams>('/admin/params')
      setParams(data.params)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '加载系统参数失败'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await api.put('/admin/params', { params })
      setSuccess('系统参数已保存')
      setTimeout(() => setSuccess(''), 3000)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '保存失败'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  function handleChange(key: string, value: string) {
    setParams((prev) => ({ ...prev, [key]: value }))
  }

  const orderedKeys = Object.keys(FIELD_CONFIG)

  return (
    <div className="p-6 max-w-2xl">
      <h2 className="text-2xl font-bold mb-1">系统参数</h2>
      <p className="text-sm text-muted-foreground mb-6">配置会计系统全局参数，影响凭证编号、报表格式等</p>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-600">
          {success}
        </div>
      )}

      {loading ? (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          加载中...
        </div>
      ) : (
        <div className="rounded-lg border bg-card">
          <div className="p-6 space-y-5">
            {orderedKeys.map((key) => {
              const config = FIELD_CONFIG[key]
              return (
                <div key={key}>
                  <label className="block text-sm font-medium mb-1.5" htmlFor={`param-${key}`}>
                    {config.label}
                  </label>
                  {config.type === 'select' && config.options ? (
                    <select
                      id={`param-${key}`}
                      value={params[key] || ''}
                      onChange={(e) => handleChange(key, e.target.value)}
                      className="w-full rounded-md border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-accent"
                    >
                      {config.options.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      id={`param-${key}`}
                      type="text"
                      value={params[key] || ''}
                      onChange={(e) => handleChange(key, e.target.value)}
                      className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                      placeholder={`请输入${config.label}`}
                    />
                  )}
                </div>
              )
            })}
          </div>
          <div className="border-t px-6 py-4 flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-md bg-accent px-6 py-2 text-sm font-medium text-white hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? '保存中...' : '保存参数'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
