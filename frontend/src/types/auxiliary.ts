export interface AuxEntity {
  id: string
  code: string
  name: string
  is_enabled: boolean
  created_at: string
}

export interface AuxLedgerRow {
  date: string
  voucher_no: string
  account_code: string
  account_name: string
  summary: string
  debit: string
  credit: string
  balance: string
  direction: 'D' | 'C'
}

export interface AuxLedgerResponse {
  entity: AuxEntity
  aux_type: string
  period: { year: number; month: number }
  opening_balance: string
  rows: AuxLedgerRow[]
  closing_balance: string
}

export interface AgingItem {
  entity_id: string
  entity_name: string
  total: string
  current: string
  days_30: string
  days_60: string
  days_90: string
  days_180: string
  days_365: string
  over_365: string
}

export interface AgingResponse {
  aux_type: string
  as_of_date: string
  items: AgingItem[]
}
