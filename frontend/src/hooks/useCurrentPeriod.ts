import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '@/stores/appStore'
import api from '@/lib/api'
import type { Period } from '@/types/period'
import { useEffect } from 'react'

/**
 * Hook for accessing the current accounting period.
 * Fetches from /periods/current and syncs to app store.
 */
export function useCurrentPeriod() {
  const { currentPeriod, setCurrentPeriod } = useAppStore()

  const query = useQuery<Period>({
    queryKey: ['current-period'],
    queryFn: async () => {
      const { data } = await api.get('/periods/current')
      return data
    },
    staleTime: 5 * 60 * 1000, // 5 min — period changes rarely
  })

  useEffect(() => {
    if (query.data) {
      setCurrentPeriod(query.data)
    }
  }, [query.data, setCurrentPeriod])

  return {
    currentPeriod: currentPeriod || query.data,
    isLoading: query.isLoading,
    error: query.error,
  }
}
