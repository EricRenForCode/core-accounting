import { create } from 'zustand'
import type { User } from '@/types/user'
import type { Permission } from '@/lib/constants'

interface UserState {
  user: User | null
  permissions: Set<Permission>
  setUser: (user: User) => void
  logout: () => void
  can: (permission: Permission) => boolean
  isAuthenticated: () => boolean
}

export const useUserStore = create<UserState>((set, get) => ({
  user: null,
  permissions: new Set(),
  setUser: (user) => set({ user, permissions: new Set(user.permissions) }),
  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ user: null, permissions: new Set() })
  },
  can: (permission) => get().permissions.has(permission),
  isAuthenticated: () => get().user !== null,
}))
