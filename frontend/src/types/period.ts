import type { PeriodStatusType } from '@/lib/constants'

export interface Period {
  id: string
  year: number
  month: number
  status: PeriodStatusType
  closed_at?: string
  closed_by?: string
}

export interface CarryForwardTemplate {
  id: string
  name: string
  description?: string
  rules: Record<string, unknown>
  sort_order: number
  is_enabled: boolean
}

export interface CarryForwardRecord {
  id: string
  period_id: string
  template_id: string
  voucher_id: string
  from_account_id: string
  to_account_id: string
  amount: string
  executed_at: string
}

export interface PeriodCheck {
  id: number
  name: string
  status: 'pass' | 'warn' | 'fail'
  detail: string
}

export interface PeriodCheckResponse {
  period_id: string
  checks: PeriodCheck[]
  summary: { pass: number; warn: number; fail: number }
  can_close: boolean
}

export interface CarryForwardResult {
  executed: number
  details: {
    template: string
    voucher_no: string
  }[]
}

export interface AccountBalance {
  id: string
  period_id: string
  account_id: string
  opening_debit: string
  opening_credit: string
  current_debit: string
  current_credit: string
  closing_debit: string
  closing_credit: string
}
