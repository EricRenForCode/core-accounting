import type { VoucherStatusType, VoucherSourceType, ReversalTypeValue } from '@/lib/constants'

export interface Voucher {
  id: string
  voucher_no: string
  date: string
  period_id: string
  attachments: number
  status: VoucherStatusType
  creator_id: string
  auditor_id: string | null
  posted_at: string | null
  source: VoucherSourceType
  ai_conversation?: Record<string, unknown>
  deleted_at?: string | null
  reversed_voucher_id?: string | null
  reversal_type?: ReversalTypeValue
  created_at: string
  updated_at: string
  entries?: VoucherEntry[]
}

export interface VoucherEntry {
  id: string
  voucher_id: string
  row_number: number
  account_id: string
  account?: AccountBrief
  summary: string
  debit_amount: string
  credit_amount: string
  quantity?: string
  price?: string
  auxiliaries?: AuxiliaryRef[]
}

export interface AccountBrief {
  id: string
  code: string
  name: string
  level: number
  type: string
  dc_type: string
}

export interface AuxiliaryRef {
  aux_type: string
  aux_entity_id: string
  entity?: AuxEntityBrief
}

export interface AuxEntityBrief {
  id: string
  code: string
  name: string
}

export interface VoucherListParams {
  page?: number
  page_size?: number
  sort?: string
  order?: 'asc' | 'desc'
  date_from?: string
  date_to?: string
  status?: VoucherStatusType
  keyword?: string
  period_id?: string
}

export interface CreateVoucherRequest {
  date: string
  period_id: string
  attachments?: number
  entries: CreateEntryRequest[]
}

export interface CreateEntryRequest {
  row_number: number
  account_id: string
  summary: string
  debit_amount: string
  credit_amount: string
  auxiliaries?: AuxiliaryRef[]
}

export interface VoucherTemplate {
  id: string
  name: string
  description?: string
  entries: Omit<CreateEntryRequest, 'row_number'>[]
  created_at: string
  updated_at: string
}
