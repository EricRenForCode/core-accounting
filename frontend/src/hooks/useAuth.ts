import { useNavigate } from '@tanstack/react-router'
import { useUserStore } from '@/stores/userStore'
import { useCallback } from 'react'

/**
 * Hook providing authentication state and actions.
 */
export function useAuth() {
  const { user, isAuthenticated, setUser, logout: storeLogout } = useUserStore()
  const navigate = useNavigate()

  const logout = useCallback(() => {
    storeLogout()
    navigate({ to: '/login' })
  }, [storeLogout, navigate])

  return {
    user,
    isAuthenticated: isAuthenticated(),
    setUser,
    logout,
  }
}
