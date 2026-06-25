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

// Financial statements (balance sheet, income, cash-flow) all share the same
// StatementItem / StatementSection shape returned by the backend
// (app/schemas/report.py: StatementItem, StatementSection).
export interface StatementAmount {
  closing: string
  opening: string
}

export interface BalanceSheetItem {
  name: string
  code?: string
  closing: string
  opening: string
}

export interface BalanceSheetSection {
  label: string
  items: BalanceSheetItem[]
  subtotal: StatementAmount
}

export interface BalanceSheetResponse {
  period: { year: number; month: number }
  template: { name: string; id: string }
  sections: BalanceSheetSection[]
  totals: {
    assets: StatementAmount
    liabilities_equity: StatementAmount
  }
}

export interface IncomeStatementResponse {
  period: { year: number; month: number }
  template: { name: string; id: string }
  sections: BalanceSheetSection[]
  totals: {
    revenue?: StatementAmount
    operating_profit?: StatementAmount
    net_profit?: StatementAmount
  }
}

export interface CashFlowStatementResponse {
  period: { year: number; month: number }
  template: { name: string; id: string }
  sections: BalanceSheetSection[]
  totals: {
    operating?: StatementAmount
    investing?: StatementAmount
    financing?: StatementAmount
    net_increase?: StatementAmount
  }
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
