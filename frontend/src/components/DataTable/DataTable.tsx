import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

export interface ColumnDef<T> {
  key: string
  header: string
  accessorKey?: keyof T
  sortable?: boolean
  className?: string
  headerClassName?: string
  cell?: (row: T) => ReactNode
  footer?: (rows: T[]) => ReactNode
}

interface DataTableProps<T> {
  columns: ColumnDef<T>[]
  data: T[]
  total: number
  page: number
  pageSize: number
  onPaginationChange: (page: number, pageSize: number) => void
  onSortChange?: (sort: string, order: 'asc' | 'desc') => void
  sort?: string
  sortOrder?: 'asc' | 'desc'
  isLoading?: boolean
  toolbar?: ReactNode
  rowActions?: (row: T) => ReactNode
  onRowClick?: (row: T) => void
  selectable?: boolean
  selectedRows?: string[]
  onSelectionChange?: (ids: string[]) => void
  getId?: (row: T) => string
  footer?: ReactNode
  emptyMessage?: string
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  isLoading,
  toolbar,
  rowActions,
  onRowClick,
  selectable,
  selectedRows = [],
  onSelectionChange,
  getId = (row) => (row.id as string) || '',
  sort,
  sortOrder,
  onSortChange,
  footer,
  emptyMessage = '暂无数据',
}: DataTableProps<T>) {
  const allSelected = data.length > 0 && data.every((row) => selectedRows.includes(getId(row)))
  const someSelected = selectedRows.length > 0 && !allSelected

  const handleSelectAll = () => {
    if (allSelected) {
      onSelectionChange?.([])
    } else {
      onSelectionChange?.(data.map((row) => getId(row)))
    }
  }

  const handleSelectRow = (id: string) => {
    const next = selectedRows.includes(id)
      ? selectedRows.filter((r) => r !== id)
      : [...selectedRows, id]
    onSelectionChange?.(next)
  }

  const handleSort = (col: ColumnDef<T>) => {
    if (!col.sortable || !onSortChange) return
    const key = col.accessorKey as string || col.key
    if (sort === key) {
      onSortChange(key, sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      onSortChange(key, 'asc')
    }
  }

  const sortIndicator = (col: ColumnDef<T>) => {
    const key = col.accessorKey as string || col.key
    if (sort !== key) return <span className="text-muted-foreground ml-1">⇅</span>
    return <span className="text-accent ml-1">{sortOrder === 'asc' ? '↑' : '↓'}</span>
  }

  if (isLoading) {
    return (
      <div className="rounded-lg border">
        {toolbar && <div className="p-4 border-b">{toolbar}</div>}
        <div className="p-8 space-y-3">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="h-8 bg-gray-100 rounded animate-pulse" style={{ animationDelay: `${i * 80}ms` }} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-lg border bg-card">
      {toolbar && <div className="p-4 border-b">{toolbar}</div>}

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-gray-50">
              {selectable && (
                <th className="w-10 px-3 py-3">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = someSelected
                    }}
                    onChange={handleSelectAll}
                    className="rounded border-gray-300"
                  />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    'px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider',
                    col.sortable && 'cursor-pointer select-none hover:text-foreground',
                    col.headerClassName,
                  )}
                  onClick={() => handleSort(col)}
                >
                  <span className="inline-flex items-center">
                    {col.header}
                    {col.sortable && sortIndicator(col)}
                  </span>
                </th>
              ))}
              {rowActions && <th className="w-20 px-4 py-3" />}
            </tr>
          </thead>
          <tbody>
            {data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (selectable ? 1 : 0) + (rowActions ? 1 : 0)}
                  className="px-4 py-16 text-center text-muted-foreground"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((row) => {
                const id = getId(row)
                const isSelected = selectedRows.includes(id)
                return (
                  <tr
                    key={id}
                    className={cn(
                      'border-b last:border-b-0 hover:bg-gray-50 transition-colors',
                      onRowClick && 'cursor-pointer',
                      isSelected && 'bg-blue-50',
                    )}
                    onClick={() => onRowClick?.(row)}
                  >
                    {selectable && (
                      <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleSelectRow(id)}
                          className="rounded border-gray-300"
                        />
                      </td>
                    )}
                    {columns.map((col) => (
                      <td key={col.key} className={cn('px-4 py-3 text-sm', col.className)}>
                        {col.cell
                          ? col.cell(row)
                          : col.accessorKey
                            ? String(row[col.accessorKey as string] ?? '')
                            : ''}
                      </td>
                    ))}
                    {rowActions && (
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        {rowActions(row)}
                      </td>
                    )}
                  </tr>
                )
              })
            )}
          </tbody>
          {footer && <tfoot className="border-t bg-gray-50">{footer}</tfoot>}
        </table>
      </div>
    </div>
  )
}
