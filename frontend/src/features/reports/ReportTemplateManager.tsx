import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { Skeleton } from '@/components/Skeleton'
import { ErrorCard } from '@/components/ErrorCard'
import { FileSpreadsheet, FileText } from 'lucide-react'

interface Template {
  id: string
  name: string
  type: string
  description: string
}

const TYPE_LABELS: Record<string, string> = {
  balance_sheet: '资产负债表',
  income: '利润表',
  cash_flow: '现金流量表',
}

const TYPE_ICONS: Record<string, typeof FileSpreadsheet> = {
  balance_sheet: FileSpreadsheet,
  income: FileText,
  cash_flow: FileSpreadsheet,
}

export default function ReportTemplateManagerPage() {
  const {
    data: templates,
    isLoading,
    error,
  } = useQuery<Template[]>({
    queryKey: ['statement-templates'],
    queryFn: async () => {
      const { data } = await api.get('/statements/templates')
      return data
    },
  })

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <ErrorCard
          title="加载模板列表失败"
          message={(error as Error)?.message || '请稍后重试'}
        />
      </div>
    )
  }

  if (!templates || templates.length === 0) {
    return (
      <div className="p-6">
        <h2 className="text-xl font-bold mb-4">报表模板管理</h2>
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground">
          <p className="text-lg">暂无可用模板</p>
          <p className="text-sm mt-2">系统将使用默认模板生成财务报表</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h2 className="text-xl font-bold mb-4">报表模板管理</h2>
      <p className="text-sm text-muted-foreground mb-6">
        以下模板用于生成资产负债表、利润表和现金流量表。导出报表时将使用对应类型的模板格式。
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {templates.map((template, idx) => {
          const Icon = TYPE_ICONS[template.type] || FileSpreadsheet
          const typeLabel = TYPE_LABELS[template.type] || template.type

          return (
            <div
              key={idx}
              className="rounded-lg border bg-card p-4 hover:shadow-sm transition-shadow"
            >
              <div className="flex items-start gap-3">
                <div className="rounded-md bg-primary/10 p-2">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-sm truncate">
                    {template.name}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {typeLabel}
                  </p>
                  <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
                    {template.description}
                  </p>
                  <div className="mt-3">
                    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
                      {template.id === 'default' ? '系统默认' : template.id}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
