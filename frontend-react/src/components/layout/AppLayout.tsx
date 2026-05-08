import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { Toaster } from 'react-hot-toast'

export function AppLayout() {
  const token = useAuthStore(s => s.token)

  if (!token) return <Navigate to="/login" replace />

  return (
    <div style={{ width: '100vw', height: '100vh', overflow: 'hidden', background: '#0f172a' }}>
      <iframe 
        src="/legacy/dashboard" 
        style={{ width: '100%', height: '100%', border: 'none' }} 
        title="VoxFlow Dashboard"
      />
      <Toaster position="top-right" />
    </div>
  )
}
