import type { ErrorCode } from '@/lib/constants'

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ApiError {
  error: {
    code: ErrorCode | string
    message: string
    detail?: Record<string, unknown>
  }
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  user: UserInfo
}

export interface RefreshRequest {
  refresh_token: string
}

export interface RefreshResponse {
  access_token: string
}

export interface UserInfo {
  id: string
  username: string
  display_name: string
  role_id: string
  role_name: string
  permissions: string[]
  is_enabled: boolean
  last_login_at?: string
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  db: boolean
  redis: boolean
  version: string
}
