import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { Toaster } from 'react-hot-toast'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { useState } from 'react'

export function AppLayout() {
  const token = useAuthStore(s => s.token)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // ── Protected route guard ──
  if (!token) return <Navigate to="/login" replace />

  return (
    <div className="app-layout">
      {/* Mobile overlay */}
      <div
        className={`mobile-overlay${sidebarOpen ? ' open' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* Mobile menu button */}
      <button
        className="mobile-menu-btn"
        onClick={() => setSidebarOpen(o => !o)}
        aria-label="Abrir menu"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="3" y1="6"  x2="21" y2="6"  />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      {/* Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main area */}
      <div className="main-area">
        <Topbar />
        <main className="main-content">
          <Outlet />
        </main>
      </div>

      <Toaster position="top-right" />
    </div>
  )
}
