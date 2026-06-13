import { useUserStore } from '@/stores/userStore'

/**
 * Hook for checking user permissions.
 * Usage: const { can } = usePermission(); if (can('voucher:audit')) ...
 */
export function usePermission() {
  const { can, permissions, user } = useUserStore()

  return {
    can,
    permissions,
    role: user?.role_name ?? null,
    isAdmin: user?.role_name === 'admin',
    isManager: user?.role_name === 'finance_manager',
  }
}
