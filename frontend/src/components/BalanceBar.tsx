import { cn } from '@/lib/utils'

interface BalanceBarProps {
  totalDebit: number
  totalCredit: number
  className?: string
}

export function BalanceBar({ totalDebit, totalCredit, className }: BalanceBarProps) {
  const diff = totalDebit - totalCredit
  const isBalanced = Math.abs(diff) < 0.01
  const formattedDebit = totalDebit.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  const formattedCredit = totalCredit.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  const formattedDiff = Math.abs(diff).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  return (
    <div className={cn('font-mono text-sm', className)}>
      <div className="flex items-center justify-between gap-6 py-2 px-4 bg-gray-50 rounded-md border">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">借方合计:</span>
          <span className="font-semibold">{formattedDebit}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">贷方合计:</span>
          <span className="font-semibold">{formattedCredit}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">差额:</span>
          <span className={cn('font-bold', isBalanced ? 'text-green-600' : 'text-red-600')}>
            {formattedDiff}
          </span>
          {isBalanced ? (
            <span className="text-green-600 text-lg">✓</span>
          ) : (
            <span className="text-red-600 text-lg">✗</span>
          )}
        </div>
      </div>
    </div>
  )
}
