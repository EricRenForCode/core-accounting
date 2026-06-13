// ─── Role Enums ───────────────────────────────────────
export const Roles = {
  FINANCE_STAFF: 'finance_staff',
  FINANCE_MANAGER: 'finance_manager',
  ADMIN: 'admin',
} as const

export type Role = (typeof Roles)[keyof typeof Roles]

export const RoleLabels: Record<Role, string> = {
  finance_staff: '财务人员',
  finance_manager: '财务经理',
  admin: '管理员',
}

// ─── Voucher Status ──────────────────────────────────
export const VoucherStatus = {
  DRAFT: 'draft',
  AUDITED: 'audited',
  POSTED: 'posted',
  REVERSED: 'reversed',
} as const

export type VoucherStatusType = (typeof VoucherStatus)[keyof typeof VoucherStatus]

export const VoucherStatusLabels: Record<VoucherStatusType, string> = {
  draft: '草稿',
  audited: '已审核',
  posted: '已记账',
  reversed: '已冲销',
}

export const VoucherStatusColors: Record<VoucherStatusType, string> = {
  draft: 'bg-gray-100 text-gray-700',
  audited: 'bg-green-100 text-green-700',
  posted: 'bg-blue-100 text-blue-700',
  reversed: 'bg-red-100 text-red-700',
}

// ─── Voucher Source ──────────────────────────────────
export const VoucherSource = {
  MANUAL: 'manual',
  TEMPLATE: 'template',
  AI: 'ai',
  IMPORT: 'import',
} as const

export type VoucherSourceType = (typeof VoucherSource)[keyof typeof VoucherSource]

// ─── Account Types ───────────────────────────────────
export const AccountType = {
  ASSET: 'asset',
  LIABILITY: 'liability',
  EQUITY: 'equity',
  REVENUE: 'revenue',
  EXPENSE: 'expense',
} as const

export type AccountTypeValue = (typeof AccountType)[keyof typeof AccountType]

export const AccountTypeLabels: Record<AccountTypeValue, string> = {
  asset: '资产',
  liability: '负债',
  equity: '权益',
  revenue: '收入',
  expense: '费用',
}

// ─── Debit/Credit Type ──────────────────────────────
export const DCType = {
  DEBIT: 'D',
  CREDIT: 'C',
} as const

export type DCTypeValue = (typeof DCType)[keyof typeof DCType]

// ─── Period Status ───────────────────────────────────
export const PeriodStatus = {
  OPEN: 'open',
  CLOSED: 'closed',
} as const

export type PeriodStatusType = (typeof PeriodStatus)[keyof typeof PeriodStatus]

// ─── Reversal Type ──────────────────────────────────
export const ReversalType = {
  FULL: 'full',
  PARTIAL: 'partial',
} as const

export type ReversalTypeValue = (typeof ReversalType)[keyof typeof ReversalType]

// ─── Auxiliary Types ────────────────────────────────
export const AuxType = {
  DEPARTMENT: '部门',
  INDIVIDUAL: '个人',
  COUNTERPARTY: '单位',
  PROJECT: '项目',
} as const

export type AuxTypeValue = (typeof AuxType)[keyof typeof AuxType]

export const AuxTypeApiPath: Record<AuxTypeValue, string> = {
  部门: 'departments',
  个人: 'individuals',
  单位: 'counterparties',
  项目: 'projects',
}

// ─── Asset Status ────────────────────────────────────
export const AssetStatus = {
  IN_USE: 'in_use',
  DISPOSED: 'disposed',
  CLEARED: 'cleared',
} as const

export type AssetStatusType = (typeof AssetStatus)[keyof typeof AssetStatus]

export const AssetStatusLabels: Record<AssetStatusType, string> = {
  in_use: '使用中',
  disposed: '已处置',
  cleared: '已清理',
}

// ─── Depreciation Methods ───────────────────────────
export const DepreciationMethod = {
  STRAIGHT: 'straight',
  DOUBLE_DECLINING: 'double_declining',
  SUM_OF_YEARS: 'sum_of_years',
} as const

export type DepreciationMethodValue = (typeof DepreciationMethod)[keyof typeof DepreciationMethod]

export const DepreciationMethodLabels: Record<DepreciationMethodValue, string> = {
  straight: '直线法',
  double_declining: '双倍余额递减法',
  sum_of_years: '年数总和法',
}

// ─── Error Codes (附录A) ────────────────────────────
export const ErrorCodes = {
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  UNAUTHORIZED: 'UNAUTHORIZED',
  INSUFFICIENT_PERMISSIONS: 'INSUFFICIENT_PERMISSIONS',
  AI_READONLY_VIOLATION: 'AI_READONLY_VIOLATION',
  VOUCHER_NOT_FOUND: 'VOUCHER_NOT_FOUND',
  ACCOUNT_NOT_FOUND: 'ACCOUNT_NOT_FOUND',
  PERIOD_NOT_FOUND: 'PERIOD_NOT_FOUND',
  TEMPLATE_NOT_FOUND: 'TEMPLATE_NOT_FOUND',
  VOUCHER_NOT_DRAFT: 'VOUCHER_NOT_DRAFT',
  VOUCHER_ALREADY_POSTED: 'VOUCHER_ALREADY_POSTED',
  PERIOD_CLOSED: 'PERIOD_CLOSED',
  PERIOD_ALREADY_CLOSED: 'PERIOD_ALREADY_CLOSED',
  UNBALANCED_VOUCHER: 'UNBALANCED_VOUCHER',
  ACCOUNT_HAS_VOUCHERS: 'ACCOUNT_HAS_VOUCHERS',
  UNBALANCED_ENTRIES: 'UNBALANCED_ENTRIES',
  RATE_LIMITED: 'RATE_LIMITED',
  AI_RATE_LIMITED: 'AI_RATE_LIMITED',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  AI_GENERATION_FAILED: 'AI_GENERATION_FAILED',
  AI_INVALID_RESPONSE: 'AI_INVALID_RESPONSE',
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',
} as const

export type ErrorCode = (typeof ErrorCodes)[keyof typeof ErrorCodes]

// ─── Permissions ─────────────────────────────────────
export const Permissions = [
  'voucher:create',
  'voucher:edit:own',
  'voucher:edit:any',
  'voucher:delete:draft',
  'voucher:audit',
  'voucher:unaudit',
  'voucher:post',
  'voucher:reverse',
  'account:read',
  'account:manage',
  'ledger:read',
  'report:read',
  'report:export',
  'period:close',
  'period:reopen',
  'aux:manage',
  'cashier:use',
  'assets:manage',
  'ai:use',
  'admin:users',
  'admin:roles',
  'admin:backup',
  'admin:audit-log',
] as const

export type Permission = (typeof Permissions)[number]

// ─── Pagination Defaults ─────────────────────────────
export const DEFAULT_PAGE_SIZE = 20
export const PAGE_SIZE_OPTIONS = [20, 50, 100] as const
