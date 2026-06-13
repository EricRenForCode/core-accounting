import type { AccountTypeValue, DCTypeValue, AuxTypeValue } from '@/lib/constants'

export interface Account {
  id: string
  code: string
  name: string
  parent_id: string | null
  level: number
  type: AccountTypeValue
  dc_type: DCTypeValue
  is_cash: boolean
  aux_types: AuxTypeValue[]
  is_quantity: boolean
  quantity_unit?: string
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface AccountTreeNode extends Account {
  children: AccountTreeNode[]
  // Computed fields for trial balance display
  opening_balance?: string
  current_debit?: string
  current_credit?: string
  closing_balance?: string
}

export interface CreateAccountRequest {
  code: string
  name: string
  parent_id?: string | null
  type: AccountTypeValue
  dc_type: DCTypeValue
  is_cash?: boolean
  aux_types?: AuxTypeValue[]
  is_quantity?: boolean
  quantity_unit?: string
}

export interface UpdateAccountRequest extends Partial<CreateAccountRequest> {
  is_enabled?: boolean
}
