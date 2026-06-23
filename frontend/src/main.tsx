import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createRouter } from '@tanstack/react-router'
import { routeTree } from './routeTree.tsx'
import api from './lib/api'
import { useUserStore } from './stores/userStore'
import type { Permission } from './lib/constants'
import './index.css'

// ⚠️ DEV：渲染前恢复已登录用户状态（有 token 但 store 为空）或自动登录。
// 实现真实 LoginPage 后请删除 devAutoLogin 及其调用。
async function devAutoLogin() {
  const existingToken = localStorage.getItem('access_token')

  // If token exists, restore user from /auth/me (store is empty after refresh)
  if (existingToken) {
    try {
      const { data } = await api.get('/auth/me')
      useUserStore.getState().setUser({
        id: data.id,
        username: data.username,
        display_name: data.display_name,
        role_id: '',
        role_name: data.role,
        permissions: data.permissions as Permission[],
        is_enabled: data.is_enabled,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      return
    } catch {
      // Token expired or invalid — clear and fall through to auto-login
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  }

  // No valid token — auto-login with dev credentials
  try {
    const { data } = await api.post('/auth/login', {
      username: 'admin',
      password: 'admin123',
    })
    localStorage.setItem('access_token', data.tokens.access_token)
    localStorage.setItem('refresh_token', data.tokens.refresh_token)
    useUserStore.getState().setUser({
      id: data.user.id,
      username: data.user.username,
      display_name: data.user.display_name,
      role_id: '',
      role_name: data.user.role,
      is_enabled: data.user.is_enabled,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      permissions: data.user.permissions as Permission[],
    })
  } catch (e) {
    console.error('[dev auto-login] failed', e)
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const router = createRouter({
  routeTree,
  context: {
    queryClient,
    auth: { isAuthenticated: false, user: null },
  },
  defaultPreload: 'intent',
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

devAutoLogin().finally(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  )
})
