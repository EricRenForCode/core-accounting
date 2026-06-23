import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import api from '@/lib/api'

// ─── Types ───────────────────────────────────────────

export interface VoucherFilters {
  page?: number
  page_size?: number
  date_from?: string
  date_to?: string
  status?: string
  keyword?: string
  period_id?: string
  sort?: string
  order?: string
}

export interface VoucherEntry {
  id: string
  row_number: number
  account_id: string
  account_code: string
  account_name: string
  summary: string
  debit_amount: string
  credit_amount: string
  auxiliaries: Array<{
    id: string
    aux_type: string
    aux_entity_id: string
    aux_entity_name: string
  }>
}

export interface Voucher {
  id: string
  voucher_no: string
  date: string
  period_id: string
  attachments: number
  status: 'draft' | 'audited' | 'posted' | 'reversed'
  creator_id: string
  creator_name: string
  auditor_id?: string
  auditor_name?: string
  posted_at?: string
  source: string
  entries: VoucherEntry[]
  created_at: string
  updated_at: string
}

export interface PaginatedVouchers {
  items: Voucher[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface CreateVoucherRequest {
  date: string
  period_id: string
  attachments: number
  entries: Array<{
    row_number: number
    account_id: string
    summary: string
    debit_amount: string
    credit_amount: string
    auxiliaries: Array<{ aux_type: string; aux_entity_id: string }>
  }>
}

export type UpdateVoucherRequest = CreateVoucherRequest

// ─── Queries ─────────────────────────────────────────

export function useVouchers(filters: VoucherFilters = {}) {
  return useQuery<PaginatedVouchers>({
    queryKey: ['vouchers', filters],
    queryFn: async () => {
      const params: Record<string, string | number> = {
        page: filters.page || 1,
        page_size: filters.page_size || 20,
      }
      if (filters.date_from) params.date_from = filters.date_from
      if (filters.date_to) params.date_to = filters.date_to
      if (filters.status) params.status = filters.status
      if (filters.keyword) params.keyword = filters.keyword
      if (filters.period_id) params.period_id = filters.period_id
      if (filters.sort) params.sort = filters.sort
      if (filters.order) params.order = filters.order
      const { data } = await api.get<PaginatedVouchers>('/vouchers', { params })
      return data
    },
    placeholderData: keepPreviousData,
  })
}

export function useVoucher(id: string) {
  return useQuery<Voucher>({
    queryKey: ['voucher', id],
    queryFn: async () => {
      const { data } = await api.get<Voucher>(`/vouchers/${id}`)
      return data
    },
    enabled: !!id,
  })
}

// ─── Mutations ───────────────────────────────────────

export function useCreateVoucher() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: CreateVoucherRequest) => {
      const { data } = await api.post<Voucher>('/vouchers', body)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vouchers'] })
    },
  })
}

export function useUpdateVoucher() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: UpdateVoucherRequest }) => {
      const { data } = await api.put<Voucher>(`/vouchers/${id}`, body)
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['vouchers'] })
      queryClient.invalidateQueries({ queryKey: ['voucher', variables.id] })
    },
  })
}

export function useDeleteVoucher() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/vouchers/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vouchers'] })
    },
  })
}

export function useBatchApprove() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (ids: string[]) => {
      // Approve each voucher individually since there's no batch endpoint yet
      const results = await Promise.allSettled(
        ids.map((id) => api.post(`/vouchers/${id}/audit`)),
      )
      const failed = results.filter((r) => r.status === 'rejected')
      if (failed.length > 0) {
        throw new Error(`${failed.length}/${ids.length} 个凭证审核失败`)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vouchers'] })
    },
  })
}

export function useBatchPost() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (ids: string[]) => {
      const results = await Promise.allSettled(
        ids.map((id) => api.post(`/vouchers/${id}/post`)),
      )
      const failed = results.filter((r) => r.status === 'rejected')
      if (failed.length > 0) {
        throw new Error(`${failed.length}/${ids.length} 个凭证记账失败`)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vouchers'] })
    },
  })
}

export function useAuditVoucher() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/vouchers/${id}/audit`)
      return data
    },
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ['vouchers'] })
      queryClient.invalidateQueries({ queryKey: ['voucher', id] })
    },
  })
}

export function useUnauditVoucher() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/vouchers/${id}/unaudit`)
      return data
    },
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ['vouchers'] })
      queryClient.invalidateQueries({ queryKey: ['voucher', id] })
    },
  })
}
