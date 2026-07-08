import { useNavigate } from '@tanstack/react-router'
import { Sparkles, BarChart3, Search, CheckCircle } from 'lucide-react'

const AI_TOOLS = [
  {
    title: '智能凭证',
    description: '用自然语言描述交易，自动生成借贷平衡的会计分录',
    icon: Sparkles,
    path: '/ai/voucher',
    color: 'text-purple-600 bg-purple-50',
  },
  {
    title: '报表解读',
    description: 'AI 分析财务报表，提供同比环比分析和风险提示',
    icon: BarChart3,
    path: '/ai/report',
    color: 'text-blue-600 bg-blue-50',
  },
  {
    title: '自然语言查询',
    description: '用中文提问，自动生成并执行安全的 SQL 查询',
    icon: Search,
    path: '/ai/query',
    color: 'text-green-600 bg-green-50',
  },
  {
    title: '期末检查',
    description: '结账前自动运行完整性检查，确保数据完整准确',
    icon: CheckCircle,
    path: '/ai/period-check',
    color: 'text-amber-600 bg-amber-50',
  },
]

export default function AIWorkspacePage() {
  const navigate = useNavigate()

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold flex items-center justify-center gap-2">
          <Sparkles className="h-6 w-6 text-primary" />
          AI 工作台
        </h2>
        <p className="text-sm text-muted-foreground mt-2">
          利用 AI 技术提升会计工作效率。支持自然语言生成凭证、报表解读、自然语言查询等功能。
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {AI_TOOLS.map((tool) => {
          const Icon = tool.icon
          return (
            <button
              key={tool.path}
              onClick={() => navigate({ to: tool.path })}
              className="rounded-lg border p-5 text-left hover:shadow-md hover:border-primary/30 transition-all hover:-translate-y-0.5"
            >
              <div className="flex items-start gap-3">
                <div className={`rounded-lg p-2.5 ${tool.color}`}>
                  <Icon className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-sm">{tool.title}</h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    {tool.description}
                  </p>
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
