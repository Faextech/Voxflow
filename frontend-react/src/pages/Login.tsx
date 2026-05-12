import { useState, useRef, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { api } from '@/api/client'
import { useAuthStore } from '@/store/auth'
import toast from 'react-hot-toast'
import './Login.css'

export default function Login() {
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState<'credentials' | '2fa'>('credentials')
  const [challengeToken, setChallengeToken] = useState<string | null>(null)
  const [showSupreme, setShowSupreme] = useState(false)

  const emailRef    = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)
  const totpRef     = useRef<HTMLInputElement>(null)
  const navigate    = useNavigate()
  const { setTokens, setUser, token } = useAuthStore()

  // Redirect already-authenticated users — use declarative Navigate to avoid
  // calling navigate() during the render phase (which causes issues in StrictMode).
  if (token) return <Navigate to="/app/dashboard" replace />

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (step === 'credentials') {
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

        if (d.requires_2fa) {
          setChallengeToken(d.challenge_token || null)
          setStep('2fa')
        } else {
          finishLogin(d)
        }
      } catch (err: unknown) {
        toast.error((err as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Credenciais inválidas')
      } finally {
        setLoading(false)
      }
    } else {
      const code = totpRef.current?.value.trim().replace(/\s/g, '') ?? ''
      if (!code || code.length !== 6) {
        toast.error('Digite o código de 6 dígitos')
        return
      }

      setLoading(true)
      try {
        const body: Record<string, string> = { code }
        if (challengeToken) body.challenge_token = challengeToken

        const res = await api.post('/auth/login/2fa', body)
        finishLogin(res.data)
      } catch (err: unknown) {
        toast.error((err as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Código inválido ou expirado.')
      } finally {
        setLoading(false)
      }
    }
  }

  function finishLogin(d: any) {
    const access_token = d.access_token ?? d.token
    const csrf_token   = d.csrf_token ?? undefined
    const user = d.user ?? {
      id:         d.user_id,
      name:       d.name,
      email:      d.email,
      role:       d.role,
      company_id: d.company_id,
    }
    setTokens(access_token, csrf_token)
    setUser(user)
    
    // Populate legacy localStorage so iframe-based dashboards can read the session
    localStorage.setItem('voxflow_token', access_token)
    localStorage.setItem('token', access_token)
    localStorage.setItem('user_id', String(user.id))
    localStorage.setItem('company_id', String(user.company_id))
    localStorage.setItem('voxflow_role', user.role || 'agent')
    localStorage.setItem('voxflow_user_name', user.name || '')
    localStorage.setItem('user_email', user.email)
    if (d.agent_id) localStorage.setItem('agent_id', String(d.agent_id))
    if (d.token_expires_in) {
      localStorage.setItem('voxflow_token_exp', String(Date.now() + d.token_expires_in * 1000))
    }

    if (user.role === 'superadmin') {
      navigate('/app/dashboard', { replace: true })
    } else {
      navigate('/app/dashboard', { replace: true })
    }
  }

  function handleEmailChange(e: React.ChangeEvent<HTMLInputElement>) {
    setShowSupreme(e.target.value.toLowerCase() === 'allan.consultoriajba@gmail.com')
  }

  function handleTotpChange(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value.replace(/\D/g, '').slice(0, 6)
    e.target.value = v
    // Auto-submit when 6 digits entered — matches legacy HTML behavior
    if (v.length === 6 && !loading) {
      handleSubmit({ preventDefault: () => {} } as FormEvent)
    }
  }

  return (
    <div className="login-page-container">
      <div className="hero-gradient"></div>
      <div className="bg-pattern"></div>

      <div className="login-card">
        <div className="login-logo">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path>
          </svg>
          <span>VoxFlow</span>
        </div>

        {showSupreme && (
          <div style={{ textAlign: 'center' }}>
            <div className="supreme-badge">Acesso Supremo</div>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {step === 'credentials' ? (
            <div id="step-credentials">
              <h2>Bem-vindo de volta</h2>
              <p className="subtitle">Acesse sua conta para começar a discar.</p>

              <div className="form-group">
                <label htmlFor="email">E-mail corporativo</label>
                <input 
                  ref={emailRef} 
                  type="email" 
                  id="email" 
                  placeholder="seu@email.com" 
                  required 
                  autoComplete="username" 
                  onChange={handleEmailChange}
                />
              </div>

              <div className="form-group">
                <label htmlFor="password">Senha</label>
                <input 
                  ref={passwordRef} 
                  type="password" 
                  id="password" 
                  placeholder="••••••••" 
                  required 
                  autoComplete="current-password" 
                />
              </div>

              <button type="submit" disabled={loading}>
                {!loading && <span>Entrar na Plataforma</span>}
                {loading && <div className="loading-spinner"></div>}
              </button>

              <div className="footer-links">
                Não tem uma conta? <a href="/register">Criar agora</a>
              </div>
            </div>
          ) : (
            <div id="step-2fa" className="step-2fa-active">
              <h2>Verificação 2FA</h2>
              <p className="subtitle">Autenticação de dois fatores ativada.</p>

              <div className="totp-info">
                <span className="icon">🔐</span>
                <span>Abra o <strong>Google Authenticator</strong> (ou app compatível) e insira o código de 6 dígitos gerado para o <strong>VoxFlow</strong>.</span>
              </div>

              <div className="form-group">
                <label htmlFor="totp-code">Código TOTP</label>
                <input
                  ref={totpRef}
                  type="text"
                  id="totp-code"
                  className="totp-code-input"
                  placeholder="000000"
                  maxLength={6}
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  autoComplete="one-time-code"
                  autoFocus
                  onChange={handleTotpChange}
                />
              </div>

              <button type="submit" disabled={loading}>
                {!loading && <span>Verificar e Entrar</span>}
                {loading && <div className="loading-spinner"></div>}
              </button>

              <span className="back-link" onClick={() => setStep('credentials')}>← Voltar para o login</span>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
