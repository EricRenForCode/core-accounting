import type { Role, Permission } from '@/lib/constants'

export interface User {
  id: string
  username: string
  display_name: string
  role_id: string
  role_name?: string
  permissions: Permission[]
  is_enabled: boolean
  last_login_at?: string
  created_at: string
  updated_at: string
}

export interface CreateUserRequest {
  username: string
  password: string
  display_name: string
  role_id: string
}

export interface UpdateUserRequest {
  display_name?: string
  role_id?: string
  is_enabled?: boolean
  password?: string
}

export interface RoleInfo {
  id: string
  name: Role
  permissions: Record<string, boolean>
}

export interface AuditLog {
  id: number
  user_id: string
  user_display_name?: string
  action: string
  resource_type: string
  resource_id: string
  old_values?: Record<string, unknown>
  new_values?: Record<string, unknown>
  ip_address: string
  created_at: string
}

export interface AuditLogParams {
  page?: number
  page_size?: number
  user_id?: string
  action?: string
  resource_type?: string
  date_from?: string
  date_to?: string
}
