import { useCurrentPeriod } from '@/hooks/useCurrentPeriod'
import { useUserStore } from '@/stores/userStore'
import { formatPeriod } from '@/lib/utils'
import { Calendar, ChevronDown, User } from 'lucide-react'
import { cn } from '@/lib/utils'

interface HeaderProps {
  className?: string
}

export function Header({ className }: HeaderProps) {
  const { currentPeriod } = useCurrentPeriod()
  const { user } = useUserStore()

  return (
    <header
      className={cn(
        'flex items-center justify-between h-14 px-4 border-b bg-white',
        className,
      )}
    >
      {/* Left: Logo */}
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-bold text-primary">
          <span className="text-accent">Core</span>Accounting
        </h1>
        <span className="text-xs text-muted-foreground bg-gray-100 px-2 py-0.5 rounded">
          v1
        </span>
      </div>

      {/* Right: Period selector + User */}
      <div className="flex items-center gap-4">
        {/* Current Period */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md border bg-gray-50 text-sm">
          <Calendar size={14} className="text-muted-foreground" />
          <span className="font-medium">
            {currentPeriod
              ? formatPeriod(currentPeriod.year, currentPeriod.month)
              : '加载中...'}
          </span>
          <ChevronDown size={12} className="text-muted-foreground" />
        </div>

        {/* User Avatar + Role */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-gray-50 cursor-pointer text-sm">
          <div className="w-7 h-7 rounded-full bg-accent text-white flex items-center justify-center text-xs font-medium">
            <User size={14} />
          </div>
          <div className="hidden sm:block">
            <div className="text-sm font-medium leading-tight">
              {user?.display_name ?? '用户'}
            </div>
            <div className="text-xs text-muted-foreground leading-tight">
              {user?.role_name ?? ''}
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
