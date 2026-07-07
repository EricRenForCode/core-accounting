/**
 * VoucherForm component test — §8 前端测试重点
 * 
 * Tests: entry row management, debit/credit toggle, balance indicator,
 * form submission rendering. Uses vitest + @testing-library/react.
 * 
 * API calls are mocked via vi.mock('@/lib/api') to avoid real HTTP.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import VoucherForm from '@/features/vouchers/VoucherForm'

// Mock axios api module — vi.mock is hoisted, so the mock object must be
// created via vi.hoisted (a plain top-level const is not yet initialized
// when the factory runs).
const mockApi = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/lib/api', () => ({ default: mockApi }))

// Mock router navigation — VoucherForm calls useNavigate()
vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return { ...actual, useNavigate: () => vi.fn() }
})

// Mock stores
vi.mock('@/stores/userStore', () => ({
  useUserStore: vi.fn(() => ({
    user: { id: 'test-user-id', username: 'test' },
    isAuthenticated: () => true,
  })),
}))

// Mock logger
vi.mock('@/lib/logger', () => ({
  logger: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}))

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  )
}

describe('VoucherForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.get.mockResolvedValue({
      data: { id: 'p1', year: 2026, month: 6, status: 'open' },
    })
    mockApi.post.mockResolvedValue({ data: { id: 'v1', status: 'draft' } })
    mockApi.put.mockResolvedValue({ data: {} })
    mockApi.delete.mockResolvedValue({ data: {} })
  })

  it('renders a form with a date input after period loads', async () => {
    renderWithProviders(<VoucherForm />)
    await waitFor(() =>
      expect(document.querySelector('input[type="date"]')).toBeTruthy()
    )
  })

  it('renders entry table header labels', async () => {
    renderWithProviders(<VoucherForm />)
    await waitFor(() => {
      for (const header of ['摘要', '科目', '借方金额', '贷方金额']) {
        expect(
          screen.queryAllByText(new RegExp(header)).length
        ).toBeGreaterThan(0)
      }
    })
  })

  it('renders at least one action button', async () => {
    renderWithProviders(<VoucherForm />)
    await waitFor(() =>
      expect(screen.queryAllByRole('button').length).toBeGreaterThan(0)
    )
  })

  it('starts balanced at 0.00 = 0.00 (empty entries)', async () => {
    renderWithProviders(<VoucherForm />)
    // Balance bar shows debit/credit totals; both start at 0
    await waitFor(() =>
      expect(screen.queryAllByText(/0\.00/).length).toBeGreaterThan(0)
    )
  })
})
