import { useState, useRef, useEffect, useLayoutEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
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
  const triggerRef = useRef<HTMLButtonElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const [coords, setCoords] = useState<{
    left: number
    top?: number
    bottom?: number
    width: number
    maxHeight: number
  } | null>(null)

  // Position the (portaled) dropdown relative to the trigger, flipping up when
  // there isn't enough room below — so it's never clipped or off-screen.
  const updateCoords = useCallback(() => {
    const el = triggerRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const spaceBelow = window.innerHeight - r.bottom
    const spaceAbove = r.top
    const desired = 320
    const openUp = spaceBelow < desired && spaceAbove > spaceBelow
    const maxHeight = Math.max(180, (openUp ? spaceAbove : spaceBelow) - 16)
    setCoords({
      left: r.left,
      top: openUp ? undefined : r.bottom + 4,
      bottom: openUp ? window.innerHeight - r.top + 4 : undefined,
      width: Math.max(r.width, 320),
      maxHeight,
    })
  }, [])

  useLayoutEffect(() => {
    if (open) updateCoords()
  }, [open, updateCoords])

  useEffect(() => {
    if (!open) return
    const handler = () => updateCoords()
    window.addEventListener('resize', handler)
    window.addEventListener('scroll', handler, true)
    return () => {
      window.removeEventListener('resize', handler)
      window.removeEventListener('scroll', handler, true)
    }
  }, [open, updateCoords])

  const { data: tree = [] } = useQuery<AccountTreeNode[]>({
    queryKey: ['accounts', 'tree'],
    queryFn: async () => {
      const { data } = await api.get('/accounts/tree')
      // Backend returns { accounts: [...], total_count }, not a bare array
      return Array.isArray(data) ? data : (data?.accounts ?? [])
    },
    staleTime: 5 * 60 * 1000,
  })

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as Node
      if (containerRef.current?.contains(target)) return
      if (dropdownRef.current?.contains(target)) return
      setOpen(false)
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
        ref={triggerRef}
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

      {open && coords &&
        createPortal(
          <div
            ref={dropdownRef}
            style={{
              position: 'fixed',
              left: coords.left,
              top: coords.top,
              bottom: coords.bottom,
              width: coords.width,
            }}
            className="z-50 flex flex-col rounded-md border bg-white shadow-lg"
          >
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
            <div className="overflow-y-auto p-1" style={{ maxHeight: coords.maxHeight }}>
              {tree.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">暂无科目数据</p>
              ) : (
                tree.map((node) => renderNode(node, 0))
              )}
            </div>
          </div>,
          document.body,
        )}
    </div>
  )
}
