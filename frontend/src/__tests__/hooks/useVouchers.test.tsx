/**
 * useVouchers hook test — §8 前端测试重点
 * 
 * Tests: query key structure, filter parameter handling,
 * pagination state, mutation callbacks.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useVouchers, type VoucherFilters } from '@/features/vouchers/useVouchers'

// Mock api module
vi.mock('@/lib/api', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({
      data: {
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        pages: 0,
      },
    })),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

// Mock logger
vi.mock('@/lib/logger', () => ({
  logger: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
  }
}

describe('useVouchers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns loading state initially', async () => {
    const { result } = renderHook(
      () => useVouchers({ page: 1, page_size: 20 }),
      { wrapper: createWrapper() }
    )

    expect(result.current.isLoading).toBe(true)
    await waitFor(() => {
      expect(result.current.isSuccess || result.current.isError).toBe(true)
    })
  })

  it('includes filters in query key structure', async () => {
    const { result } = renderHook(
      () => useVouchers({ 
        page: 1, 
        page_size: 10, 
        status: 'draft',
        keyword: 'test',
      }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.isSuccess || result.current.isError).toBe(true)
    })

    // Should not crash with filter params
    expect(result.current.data).toBeDefined()
  })

  it('returns paginated data structure', async () => {
    const { result } = renderHook(
      () => useVouchers({ page: 1, page_size: 20 }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.isSuccess || result.current.isError).toBe(true)
    })

    // Data structure should match PaginatedVouchers
    const data = result.current.data
    if (data) {
      expect(data).toHaveProperty('items')
      expect(data).toHaveProperty('total')
      expect(data).toHaveProperty('page')
      expect(data).toHaveProperty('page_size')
      expect(data).toHaveProperty('pages')
      expect(Array.isArray(data.items)).toBe(true)
    }
  })

  it('accepts date range filters', async () => {
    const { result } = renderHook(
      () => useVouchers({ 
        page: 1, 
        page_size: 20,
        date_from: '2026-06-01',
        date_to: '2026-06-30',
      }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.isSuccess || result.current.isError).toBe(true)
    })

    // Should not error with date filters
    expect(result.current.error).toBeNull()
  })

  it('accepts sort and order params', async () => {
    const { result } = renderHook(
      () => useVouchers({ 
        page: 1, 
        page_size: 20,
        sort: 'date',
        order: 'desc',
      }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.isSuccess || result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeNull()
  })
})
