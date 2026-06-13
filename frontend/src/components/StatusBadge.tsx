import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  status: string
  label: string
  className?: string
}

const colorMap: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700 border-gray-300',
  audited: 'bg-green-100 text-green-700 border-green-300',
  posted: 'bg-blue-100 text-blue-700 border-blue-300',
  reversed: 'bg-red-100 text-red-700 border-red-300',
  open: 'bg-green-100 text-green-700 border-green-300',
  closed: 'bg-gray-100 text-gray-500 border-gray-300',
  in_use: 'bg-blue-100 text-blue-700 border-blue-300',
  disposed: 'bg-yellow-100 text-yellow-700 border-yellow-300',
  cleared: 'bg-gray-100 text-gray-500 border-gray-300',
  pass: 'bg-green-100 text-green-700 border-green-300',
  warn: 'bg-yellow-100 text-yellow-700 border-yellow-300',
  fail: 'bg-red-100 text-red-700 border-red-300',
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
        colorMap[status] ?? 'bg-gray-100 text-gray-700 border-gray-300',
        className,
      )}
    >
      {label}
    </span>
  )
}
