import { cn } from '@/lib/utils'

interface ErrorCardProps {
  title?: string
  message: string
  onRetry?: () => void
  className?: string
}

export function ErrorCard({ title = '加载失败', message, onRetry, className }: ErrorCardProps) {
  return (
    <div className={cn('rounded-lg border border-destructive/50 bg-destructive/5 p-6', className)}>
      <div className="flex items-start gap-3">
        <div className="text-destructive text-xl mt-0.5">⚠</div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-destructive mb-1">{title}</h3>
          <p className="text-sm text-muted-foreground">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 inline-flex items-center rounded-md border border-destructive/30 px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors"
            >
              重试
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
