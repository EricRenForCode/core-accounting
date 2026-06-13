import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DataTable } from '@/components/DataTable/DataTable'
import type { ColumnDef } from '@/components/DataTable/DataTable'

type TestRow = Record<string, unknown> & {
  id: string
  name: string
  amount: number
  status: string
}

const columns: ColumnDef<TestRow>[] = [
  { key: 'name', header: '名称', accessorKey: 'name', sortable: true },
  {
    key: 'amount',
    header: '金额',
    accessorKey: 'amount',
    sortable: true,
    cell: (row) => `¥${row.amount.toLocaleString()}`,
  },
  { key: 'status', header: '状态', accessorKey: 'status' },
]

const testData: TestRow[] = [
  { id: '1', name: '差旅费', amount: 5000, status: '已记账' },
  { id: '2', name: '办公费', amount: 3000, status: '草稿' },
  { id: '3', name: '折旧费', amount: 12000, status: '已审核' },
]

const defaultProps = {
  columns,
  data: testData,
  total: 3,
  page: 1,
  pageSize: 20,
  onPaginationChange: vi.fn(),
}

describe('DataTable', () => {
  it('renders header columns', () => {
    render(<DataTable {...defaultProps} />)
    expect(screen.getByText('名称')).toBeInTheDocument()
    expect(screen.getByText('金额')).toBeInTheDocument()
    expect(screen.getByText('状态')).toBeInTheDocument()
  })

  it('renders all rows', () => {
    render(<DataTable {...defaultProps} />)
    expect(screen.getByText('差旅费')).toBeInTheDocument()
    expect(screen.getByText('办公费')).toBeInTheDocument()
    expect(screen.getByText('折旧费')).toBeInTheDocument()
  })

  it('renders custom cell formatter', () => {
    render(<DataTable {...defaultProps} />)
    expect(screen.getByText('¥5,000')).toBeInTheDocument()
  })

  it('shows empty state when no data', () => {
    render(<DataTable {...defaultProps} data={[]} total={0} />)
    expect(screen.queryByText('差旅费')).not.toBeInTheDocument()
  })

  it('shows custom empty message', () => {
    render(<DataTable {...defaultProps} data={[]} total={0} emptyMessage="没有记录" />)
    expect(screen.getByText('没有记录')).toBeInTheDocument()
  })

  it('renders loading skeleton', () => {
    const { container } = render(<DataTable {...defaultProps} isLoading={true} />)
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('calls onSortChange when clicking sortable header', () => {
    const onSortChange = vi.fn()
    render(<DataTable {...defaultProps} onSortChange={onSortChange} />)
    fireEvent.click(screen.getByText('名称'))
    expect(onSortChange).toHaveBeenCalledWith('name', 'asc')
  })

  it('toggles sort direction on second click', () => {
    const onSortChange = vi.fn()
    render(
      <DataTable
        {...defaultProps}
        onSortChange={onSortChange}
        sort="name"
        sortOrder="asc"
      />,
    )
    fireEvent.click(screen.getByText('名称'))
    expect(onSortChange).toHaveBeenCalledWith('name', 'desc')
  })

  it('renders checkboxes when selectable', () => {
    render(<DataTable {...defaultProps} selectable={true} onSelectionChange={vi.fn()} />)
    const checkboxes = screen.getAllByRole('checkbox')
    expect(checkboxes.length).toBeGreaterThan(0)
  })

  it('calls onRowClick when row is clicked', () => {
    const onRowClick = vi.fn()
    render(<DataTable {...defaultProps} onRowClick={onRowClick} />)
    fireEvent.click(screen.getByText('差旅费'))
    expect(onRowClick).toHaveBeenCalledWith(testData[0])
  })
})
