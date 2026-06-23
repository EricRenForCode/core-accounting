import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import type { AccountTreeNode } from '@/types/account'
import { cn } from '@/lib/utils'

export interface SelectedAccount {
  id: string
  code: string
  name: string
  aux_types: string[]
}

interface AccountPickerProps {
  value?: string
  onChange: (account: SelectedAccount) => void
  disabled?: boolean
  excludeIds?: string[]
  filter?: (account: AccountTreeNode) => boolean
  placeholder?: string
  className?: string
}

export function AccountPicker({
  value,
  onChange,
  disabled = false,
  excludeIds,
  filter,
  placeholder = '选择科目...',
  className,
}: AccountPickerProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  const containerRef = useRef<HTMLDivElement>(null)

  const { data: tree = [] } = useQuery<AccountTreeNode[]>({
    queryKey: ['accounts', 'tree'],
    queryFn: async () => {
      const { data } = await api.get('/accounts/tree')
      return data
    },
    staleTime: 5 * 60 * 1000,
  })

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Find selected account display
  const findAccount = useCallback(
    (id: string, nodes: AccountTreeNode[]): AccountTreeNode | null => {
      for (const node of nodes) {
        if (node.id === id) return node
        if (node.children.length) {
          const found = findAccount(id, node.children)
          if (found) return found
        }
      }
      return null
    },
    [],
  )

  const selectedAccount = value ? findAccount(value, tree) : null

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const shouldShow = (node: AccountTreeNode): boolean => {
    if (excludeIds?.includes(node.id)) return false
    if (filter && !filter(node)) return false
    if (!search) return true
    return (
      node.code.includes(search) ||
      node.name.toLowerCase().includes(search.toLowerCase()) ||
      node.code.replace(/-/g, '').includes(search.replace(/-/g, ''))
    )
  }

  const renderNode = (node: AccountTreeNode, depth: number): React.ReactNode => {
    if (!shouldShow(node)) {
      // Still render children if they match
      const hasMatchingChildren = node.children.some((c) => shouldShow(c) || c.children.length > 0)
      if (!hasMatchingChildren) return null
    }

    const hasChildren = node.children.length > 0
    const isExpanded = expandedIds.has(node.id)
    const isSelected = value === node.id
    const indent = depth * 20

    return (
      <div key={node.id}>
        <button
          type="button"
          className={cn(
            'flex w-full items-center gap-1 px-2 py-1.5 text-sm hover:bg-gray-100 rounded',
            isSelected && 'bg-blue-50 text-accent font-medium',
          )}
          style={{ paddingLeft: `${8 + indent}px` }}
          onClick={() => {
            onChange({ id: node.id, code: node.code, name: node.name, aux_types: node.aux_types || [] })
            setOpen(false)
          }}
        >
          {hasChildren ? (
            <span
              className="flex-shrink-0 w-4 text-center text-xs text-muted-foreground cursor-pointer"
              onClick={(e) => {
                e.stopPropagation()
                toggleExpand(node.id)
              }}
            >
              {isExpanded ? '▼' : '▶'}
            </span>
          ) : (
            <span className="w-4" />
          )}
          <span className="text-muted-foreground font-mono text-xs w-16 text-left flex-shrink-0">
            {node.code}
          </span>
          <span className="truncate">{node.name}</span>
        </button>
        {hasChildren && isExpanded &&
          node.children.map((child) => renderNode(child, depth + 1))}
      </div>
    )
  }

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(!open)}
        className={cn(
          'flex w-full items-center rounded-md border bg-card px-3 py-2 text-sm',
          'focus:outline-none focus:ring-2 focus:ring-accent',
          disabled && 'opacity-50 cursor-not-allowed',
          !selectedAccount && 'text-muted-foreground',
        )}
      >
        {selectedAccount ? (
          <>
            <span className="font-mono text-xs text-muted-foreground mr-2">
              {selectedAccount.code}
            </span>
            <span>{selectedAccount.name}</span>
          </>
        ) : (
          placeholder
        )}
        <span className="ml-auto text-muted-foreground">▼</span>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full min-w-[320px] rounded-md border bg-white shadow-lg">
          <div className="p-2 border-b">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索科目编码/名称..."
              className="w-full rounded border px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
              autoFocus
            />
          </div>
          <div className="max-h-64 overflow-y-auto p-1">
            {tree.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">暂无科目数据</p>
            ) : (
              tree.map((node) => renderNode(node, 0))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
