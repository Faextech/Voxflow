import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { useDialerStore } from '@/store/dialer'
import { LogOut, Moon, Sun } from 'lucide-react'
import { api } from '@/api/client'
import { useState } from 'react'

function useDarkMode() {
  // Initialize lazily from localStorage/media query — avoids setState-in-effect lint error
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem('theme')
    const prefersDark = saved ? saved === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches
    document.documentElement.classList.toggle('dark', prefersDark)
    return prefersDark
  })
  function toggle() {
    const next = !dark
    document.documentElement.classList.toggle('dark', next)
    localStorage.setItem('theme', next ? 'dark' : 'light')
    setDark(next)
  }
  return { dark, toggle }
}

export function Topbar() {
  const navigate = useNavigate()
  const user     = useAuthStore(s => s.user)
  const logout   = useAuthStore(s => s.logout)
  const session  = useDialerStore(s => s.session)
  const { dark, toggle } = useDarkMode()

  async function handleLogout() {
    try { await api.post('/auth/logout') } catch { /* best-effort */ }
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="topbar">
      <div className="topbar-title">
        {session ? (
          <div className={`dialer-pill ${session.status}`}>
            <span className="dot" />
            Discador: {session.campaign_name} — {session.leads_called}/{session.leads_total}
          </div>
        ) : (
          <div>
            <h2>VoxFlow</h2>
            <p>Plataforma de discagem inteligente</p>
          </div>
        )}
      </div>

      <div className="topbar-right">
        <button
          onClick={toggle}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text-secondary)', padding: '6px', borderRadius: '8px',
            display: 'flex', transition: 'color 0.15s',
          }}
          title={dark ? 'Modo claro' : 'Modo escuro'}
        >
          {dark ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-primary)' }}>
          <div style={{
            width: '30px', height: '30px', borderRadius: '50%',
            background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: '13px', fontWeight: '700',
          }}>
            {(user?.name ?? user?.email ?? 'U').charAt(0).toUpperCase()}
          </div>
          <div>
            <div style={{ fontWeight: '500', lineHeight: 1.2 }}>{user?.name ?? user?.email ?? 'Usuário'}</div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.2 }}>{user?.role}</div>
          </div>
        </div>

        <button
          onClick={handleLogout}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            fontSize: '12px', color: 'var(--text-secondary)',
            background: 'none', border: 'none', cursor: 'pointer',
            padding: '6px 10px', borderRadius: '8px', transition: 'all 0.15s',
            fontFamily: 'inherit',
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--accent-red)'; (e.currentTarget as HTMLButtonElement).style.background = 'rgba(220,38,38,0.08)' }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-secondary)'; (e.currentTarget as HTMLButtonElement).style.background = 'none' }}
        >
          <LogOut size={14} /> Sair
        </button>
      </div>
    </div>
  )
}
