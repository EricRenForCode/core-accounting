import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useUserStore } from '@/stores/userStore'

// 10 分钟无操作自动登出；登出前 1 分钟弹出提醒倒计时。
const IDLE_LIMIT_MS = 10 * 60 * 1000
const WARN_BEFORE_MS = 60 * 1000
const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'click']

export function IdleLogout() {
  const navigate = useNavigate()
  const logout = useUserStore((s) => s.logout)
  const user = useUserStore((s) => s.user)

  const lastActivityRef = useRef<number>(Date.now())
  const warningOpenRef = useRef<boolean>(false)
  const loggedOutRef = useRef<boolean>(false)
  const [warningOpen, setWarningOpen] = useState(false)
  const [remaining, setRemaining] = useState(WARN_BEFORE_MS / 1000)

  const doLogout = useCallback(() => {
    if (loggedOutRef.current) return
    loggedOutRef.current = true
    logout()
    navigate({ to: '/login' })
  }, [logout, navigate])

  const stayLoggedIn = useCallback(() => {
    lastActivityRef.current = Date.now()
    warningOpenRef.current = false
    setWarningOpen(false)
  }, [])

  useEffect(() => {
    // Only run while authenticated.
    if (!user) return

    loggedOutRef.current = false
    lastActivityRef.current = Date.now()

    const onActivity = () => {
      // Ignore activity while the warning is up — the user must explicitly
      // choose to stay, so the countdown stays meaningful.
      if (warningOpenRef.current) return
      lastActivityRef.current = Date.now()
    }
    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, onActivity, { passive: true }))

    const interval = window.setInterval(() => {
      const idle = Date.now() - lastActivityRef.current
      if (idle >= IDLE_LIMIT_MS) {
        doLogout()
        return
      }
      if (idle >= IDLE_LIMIT_MS - WARN_BEFORE_MS) {
        if (!warningOpenRef.current) {
          warningOpenRef.current = true
          setWarningOpen(true)
        }
        setRemaining(Math.max(0, Math.ceil((IDLE_LIMIT_MS - idle) / 1000)))
      }
    }, 1000)

    return () => {
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, onActivity))
      window.clearInterval(interval)
    }
  }, [user, doLogout])

  if (!user || !warningOpen) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-lg border bg-white p-6 shadow-lg">
        <h3 className="text-lg font-bold">即将自动登出</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          您已 {Math.floor((IDLE_LIMIT_MS - WARN_BEFORE_MS) / 60000)} 分钟未操作，将在{' '}
          <span className="font-mono font-bold text-red-600">{remaining}</span> 秒后自动退出登录。
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={doLogout}
            className="rounded-md border px-4 py-2 text-sm text-muted-foreground hover:bg-gray-50"
          >
            立即登出
          </button>
          <button
            type="button"
            onClick={stayLoggedIn}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90"
          >
            继续操作
          </button>
        </div>
      </div>
    </div>
  )
}
