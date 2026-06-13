import type { AssetStatusType, DepreciationMethodValue } from '@/lib/constants'

export interface FixedAsset {
  id: string
  code: string
  name: string
  category: string
  purchase_date: string
  purchase_amount: string
  salvage_value: string
  useful_life_months: number
  depreciation_method: DepreciationMethodValue
  monthly_depreciation: string
  accumulated_depreciation: string
  net_value: string
  status: AssetStatusType
  dept_id: string | null
  dept_name?: string
  created_at: string
}

export interface CreateAssetRequest {
  code: string
  name: string
  category: string
  purchase_date: string
  purchase_amount: number
  salvage_value: number
  useful_life_months: number
  depreciation_method: DepreciationMethodValue
  dept_id?: string
}

export interface UpdateAssetRequest extends Partial<CreateAssetRequest> {
  status?: AssetStatusType
}

export interface DepreciationSummary {
  period: { year: number; month: number }
  total_monthly: string
  total_accumulated: string
  by_category: {
    category: string
    count: number
    monthly: string
    accumulated: string
  }[]
}

export interface AssetListParams {
  page?: number
  page_size?: number
  status?: AssetStatusType
  dept_id?: string
  category?: string
}
