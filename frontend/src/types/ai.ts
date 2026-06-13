export interface AIVoucherGenerationRequest {
  description: string
  period_id: string
}

export interface AIVoucherEntry {
  row_number: number
  account: {
    id: string
    code: string
    name: string
  }
  summary: string
  debit_amount: string
  credit_amount: string
  auxiliaries: {
    aux_type: string
    entity: {
      id: string
      name: string
    }
  }[]
}

export interface AIVoucherGenerationResponse {
  conversation_id: string
  entries: AIVoucherEntry[]
  is_balanced: boolean
  matched_accounts: string[]
  ai_notes?: string
}

export interface AIVoucherRefineRequest {
  conversation_id: string
  refinement: string
}

export interface AIReportInterpretRequest {
  period_id: string
  report_type: 'balance_sheet' | 'income' | 'cash_flow'
}

export interface AIReportInterpretResponse {
  summary: string
  highlights: string[]
  risks: string[]
  recommendations: string[]
}

export interface AIPeriodCheckRequest {
  period_id: string
}

export interface AINLQueryRequest {
  question: string
  conversation_id?: string
}

export interface AINLQueryResponse {
  conversation_id: string
  question: string
  sql: string
  columns: string[]
  rows: string[][]
  row_count: number
  execution_time_ms: number
}

export interface AINLQueryExplainRequest {
  sql: string
}

export interface AINLQueryExplainResponse {
  explanation: string
}

export interface AIConversationMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}
