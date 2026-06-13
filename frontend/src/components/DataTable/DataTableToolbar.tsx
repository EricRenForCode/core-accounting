import type { ReactNode } from 'react'

interface DataTableToolbarProps {
  children: ReactNode
  className?: string
}

export function DataTableToolbar({ children, className }: DataTableToolbarProps) {
  return (
    <div className={`flex flex-wrap items-center gap-3 ${className ?? ''}`}>
      {children}
    </div>
  )
}
