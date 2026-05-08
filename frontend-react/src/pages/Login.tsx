import { useState, useRef, type FormEvent, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
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

  useEffect(() => {
    document.documentElement.classList.remove('dark')
  }, [])

  if (token) {
    navigate('/app/dashboard', { replace: true })
    return null
  }

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
      } catch (err: any) {
        toast.error(err?.response?.data?.error ?? 'Credenciais inválidas')
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
        const body: any = { code }
        if (challengeToken) body.challenge_token = challengeToken

        const res = await api.post('/auth/login/2fa', body)
        finishLogin(res.data)
      } catch (err: any) {
        toast.error(err?.response?.data?.error ?? 'Código inválido ou expirado.')
      } finally {
        setLoading(false)
      }
    }
  }

  function finishLogin(d: any) {
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
    
    if (user.role === 'superadmin') {
      window.location.href = '/admin'
    } else {
      navigate('/app/dashboard', { replace: true })
    }
  }

  function handleEmailChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.value.toLowerCase() === 'allan.consultoriajba@gmail.com') {
      setShowSupreme(true)
    } else {
      setShowSupreme(false)
    }
  }

  return (
    <div className="login-page-container">
      <div className="hero-gradient"></div>
      <div className="bg-pattern"></div>

      <div className="login-card">
        <div className="login-logo">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>
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
            <div id="step-2fa" style={{ display: 'block', animation: 'fadeSlideIn 0.3s ease' }}>
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
                  onChange={(e) => {
                    const v = e.target.value.replace(/\D/g, '').slice(0, 6)
                    e.target.value = v
                  }}
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
