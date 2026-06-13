import { cn } from '@/lib/utils'

interface SkeletonProps {
  className?: string
  variant?: 'text' | 'card' | 'table-row' | 'circle'
  count?: number
}

export function Skeleton({ className, variant = 'text', count = 1 }: SkeletonProps) {
  const baseClasses = 'animate-pulse bg-gray-200 rounded'

  const variantClasses: Record<string, string> = {
    text: 'h-4 w-full',
    card: 'h-32 w-full rounded-lg',
    'table-row': 'h-12 w-full rounded',
    circle: 'h-10 w-10 rounded-full',
  }

  const items = Array.from({ length: count }, (_, i) => (
    <div key={i} className={cn(baseClasses, variantClasses[variant], className)} />
  ))

  if (count === 1) return items[0]

  return <div className="space-y-2">{items}</div>
}

/** Pre-built skeleton for a data table loading state */
export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-2">
      <div className="h-10 bg-gray-100 rounded animate-pulse" />
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="flex gap-4">
          {Array.from({ length: cols }, (_, c) => (
            <div key={c} className="h-8 flex-1 bg-gray-100 rounded animate-pulse" style={{ animationDelay: `${r * 100}ms` }} />
          ))}
        </div>
      ))}
    </div>
  )
}
