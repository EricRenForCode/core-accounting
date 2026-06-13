import { Outlet } from '@tanstack/react-router'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

export function AppShell() {

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-background">
      {/* Header */}
      <Header />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar />

        {/* Main content */}
        <main
          className="flex-1 overflow-y-auto"
          style={{
            marginLeft: 0,
          }}
        >
          <Outlet />
        </main>
      </div>

      {/* Status Bar */}
      <footer className="flex items-center justify-between h-6 px-4 border-t bg-gray-50 text-xs text-muted-foreground">
        <span>在线</span>
        <span>CoreAccounting v1.0</span>
        <span>{new Date().toLocaleDateString('zh-CN')}</span>
      </footer>
    </div>
  )
}
