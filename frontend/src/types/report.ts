export interface TrialBalanceRow {
  account: {
    id: string
    code: string
    name: string
    level: number
  }
  opening_balance: string
  current_debit: string
  current_credit: string
  closing_balance: string
  children: TrialBalanceRow[]
}

export interface TrialBalanceResponse {
  period: { year: number; month: number }
  rows: TrialBalanceRow[]
  summary: {
    total_opening_debit: string
    total_opening_credit: string
    total_current_debit: string
    total_current_credit: string
    total_closing_debit: string
    total_closing_credit: string
  }
}

export interface GeneralLedgerRow {
  date: string
  voucher_no: string
  summary: string
  debit: string
  credit: string
  balance: string
  direction: 'D' | 'C'
}

export interface GeneralLedgerResponse {
  account: { id: string; code: string; name: string }
  period: { year: number; month: number }
  opening_balance: string
  opening_direction: 'D' | 'C'
  rows: GeneralLedgerRow[]
  closing_balance: string
  closing_direction: 'D' | 'C'
}

export interface DetailLedgerRow {
  date: string
  voucher_no: string
  summary: string
  debit: string
  credit: string
  balance: string
  direction: 'D' | 'C'
}

export interface DetailLedgerResponse {
  account: { id: string; code: string; name: string }
  period: { year: number; month: number }
  opening_balance: string
  rows: DetailLedgerRow[]
  closing_balance: string
}

export interface JournalRow {
  date: string
  voucher_no: string
  account_code: string
  account_name: string
  summary: string
  debit: string
  credit: string
}

export interface JournalResponse {
  period: { year: number; month: number }
  rows: JournalRow[]
}

export interface BalanceSheetItem {
  name: string
  closing: string
  opening: string
}

export interface BalanceSheetSection {
  label: string
  items: BalanceSheetItem[]
  subtotal: { closing: string; opening: string }
}

export interface BalanceSheetResponse {
  period: { year: number; month: number }
  template: { name: string; id: string }
  sections: BalanceSheetSection[]
  totals: {
    assets: { closing: string; opening: string }
    liabilities_equity: { closing: string; opening: string }
  }
}

export interface IncomeStatementResponse {
  period: { year: number; month: number }
  template: { name: string; id: string }
  sections: {
    label: string
    items: { name: string; current: string; cumulative: string }[]
    subtotal: { current: string; cumulative: string }
  }[]
  net_profit: { current: string; cumulative: string }
}

export interface CashFlowStatementResponse {
  period: { year: number; month: number }
  template: { name: string; id: string }
  sections: {
    label: string
    items: { name: string; amount: string }[]
    subtotal: string
  }[]
  net_increase: string
}

export interface ExportRequest {
  type: string
  period_id: string
  format: 'excel' | 'pdf'
}

export interface DashboardSummary {
  period: { id: string; year: number; month: number }
  voucher_counts: {
    draft: number
    audited: number
    posted: number
    total: number
  }
  trial_balance: {
    total_debit: string
    total_credit: string
    is_balanced: boolean
  }
  recent_activity: {
    action: string
    voucher_no: string
    user: string
    at: string
  }[]
}
