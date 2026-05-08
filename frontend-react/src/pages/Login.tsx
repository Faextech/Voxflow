import { useState, useRef, type FormEvent, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/client'
import { useAuthStore } from '@/store/auth'
import toast from 'react-hot-toast'

export default function Login() {
  const [loading, setLoading] = useState(false)
  const emailRef    = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)
  const navigate    = useNavigate()
  const { setTokens, setUser, token } = useAuthStore()

  // Force dark on login page
  useEffect(() => {
    document.documentElement.classList.add('dark')
  }, [])

  // If already logged in, go straight to dashboard
  if (token) {
    navigate('/app/dashboard', { replace: true })
    return null
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    // Read from DOM refs — captures autofill values that bypass React's onChange
    const email    = emailRef.current?.value    ?? ''
    const password = passwordRef.current?.value ?? ''

    if (!email || !password) {
      toast.error('Preencha e-mail e senha')
      return
    }

    setLoading(true)
    try {
      const res = await api.post('/auth/login', { email, password })
      const d = res.data
      // Flask returns 'token' or 'access_token' depending on endpoint version
      const access_token = d.access_token ?? d.token
      const csrf_token   = d.csrf_token ?? null
      const user = d.user ?? {
        id:         d.user_id,
        name:       d.name,
        email:      d.email,
        role:       d.role,
        company_id: d.company_id,
      }
      setTokens(access_token, csrf_token)
      setUser(user)
      navigate('/app/dashboard', { replace: true })
    } catch (err: any) {
      toast.error(err?.response?.data?.error ?? 'Credenciais inválidas')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', background: '#0f172a',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px',
    }}>
      <div style={{ width: '100%', maxWidth: '400px' }}>
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 800, color: '#fff', letterSpacing: '-0.5px' }}>
            Vox<span style={{ color: '#60a5fa' }}>Flow</span>
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '14px', marginTop: '6px' }}>
            Plataforma de discagem inteligente
          </p>
        </div>

        <div className="panel" style={{ background: '#1e293b', border: '1px solid #334155' }}>
          <div className="panel-body" style={{ padding: '28px' }}>
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="field">
                <label style={{ color: '#94a3b8' }}>E-mail</label>
                <input
                  ref={emailRef}
                  type="email"
                  name="email"
                  autoComplete="email"
                  placeholder="seu@email.com"
                  style={{ background: 'rgba(0,0,0,0.25)', borderColor: '#334155', color: '#f1f5f9' }}
                />
              </div>
              <div className="field">
                <label style={{ color: '#94a3b8' }}>Senha</label>
                <input
                  ref={passwordRef}
                  type="password"
                  name="password"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  style={{ background: 'rgba(0,0,0,0.25)', borderColor: '#334155', color: '#f1f5f9' }}
                />
              </div>
              <button
                type="submit"
                className="btn btn-accent btn-lg"
                disabled={loading}
                style={{ marginTop: '8px', width: '100%', justifyContent: 'center' }}
              >
                {loading && <span className="spinner" />}
                {loading ? 'Entrando...' : 'Entrar'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
