import { create } from 'zustand'
import type { Period } from '@/types/period'

interface AppState {
  sidebarOpen: boolean
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  currentPeriod: Period | null
  setCurrentPeriod: (period: Period) => void
}

export const useAppStore = create<AppState>((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  currentPeriod: null,
  setCurrentPeriod: (period) => set({ currentPeriod: period }),
}))
