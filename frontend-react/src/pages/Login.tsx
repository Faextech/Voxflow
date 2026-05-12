import { useState, useRef, type FormEvent, useEffect } from 'react'
import { Navigate, useNavigate, Link } from 'react-router-dom'
import { api } from '@/api/client'
import { useAuthStore } from '@/store/auth'
import toast from 'react-hot-toast'
import { PhoneCall, ShieldCheck, Mail, Lock, ArrowRight, Loader2, ChevronLeft, ShieldAlert } from 'lucide-react'

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

  // Redirect if already authenticated
  if (token) return <Navigate to="/app/dashboard" replace />

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (step === 'credentials') {
      const email    = emailRef.current?.value    ?? ''
      const password = passwordRef.current?.value ?? ''

      if (!email || !password) {
        toast.error('Por favor, preencha todos os campos.')
        return
      }

      setLoading(true)
      try {
        const res = await api.post('/auth/login', { email, password })
        const d = res.data

        if (d.requires_2fa) {
          setChallengeToken(d.challenge_token || null)
          setStep('2fa')
          toast.success('Credenciais válidas! Digite o código 2FA.')
        } else {
          finishLogin(d)
        }
      } catch (err: any) {
        const msg = err.response?.data?.error || 'Erro ao realizar login. Verifique suas credenciais.'
        toast.error(msg)
      } finally {
        setLoading(false)
      }
    } else {
      const code = totpRef.current?.value.trim().replace(/\s/g, '') ?? ''
      if (!code || code.length !== 6) {
        toast.error('O código deve ter 6 dígitos.')
        return
      }

      setLoading(true)
      try {
        const body: Record<string, string> = { code }
        if (challengeToken) body.challenge_token = challengeToken

        const res = await api.post('/auth/login/2fa', body)
        finishLogin(res.data)
      } catch (err: any) {
        const msg = err.response?.data?.error || 'Código inválido ou expirado.'
        toast.error(msg)
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
    
    // Legacy sync
    localStorage.setItem('voxflow_token', access_token)
    localStorage.setItem('token', access_token)
    localStorage.setItem('user_id', String(user.id))
    
    toast.success(`Bem-vindo de volta, ${user.name}!`)
    navigate('/app/dashboard', { replace: true })
  }

  function handleEmailChange(e: React.ChangeEvent<HTMLInputElement>) {
    setShowSupreme(e.target.value.toLowerCase() === 'allan.consultoriajba@gmail.com')
  }

  function handleTotpChange(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value.replace(/\D/g, '').slice(0, 6)
    e.target.value = v
    if (v.length === 6 && !loading) {
      handleSubmit({ preventDefault: () => {} } as FormEvent)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 relative overflow-hidden font-inter selection:bg-brand-500/30">
      <style>{`
        .login-glass {
          background: rgba(15, 23, 42, 0.6);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .supreme-glow {
          box-shadow: 0 0 40px rgba(234, 179, 8, 0.2);
          border-color: rgba(234, 179, 8, 0.4);
        }
        .input-focus:focus {
          border-color: #16a34a;
          box-shadow: 0 0 0 2px rgba(22, 163, 74, 0.2);
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-slide-up { animation: slideUp 0.5s ease-out forwards; }
      `}</style>

      {/* Decorative Blobs */}
      <div className="absolute top-0 -left-20 w-96 h-96 bg-brand-500/10 rounded-full blur-[120px]"></div>
      <div className="absolute bottom-0 -right-20 w-96 h-96 bg-blue-500/10 rounded-full blur-[120px]"></div>

      <div className={`w-full max-w-md p-8 login-glass rounded-3xl shadow-2xl relative z-10 animate-slide-up ${showSupreme ? 'supreme-glow' : ''}`}>
        <div className="text-center mb-10">
          <Link to="/" className="inline-flex items-center space-x-2 group mb-6">
            <div className="bg-brand-500 p-2 rounded-xl group-hover:rotate-12 transition-transform shadow-lg shadow-brand-500/20">
              <PhoneCall className="h-6 w-6 text-white" />
            </div>
            <span className="text-2xl font-bold text-white tracking-tight">VoxFlow</span>
          </Link>
          
          {step === 'credentials' ? (
            <>
              <h2 className="text-2xl font-bold text-white">Bem-vindo de volta</h2>
              <p className="text-slate-400 text-sm mt-2">Acesse sua conta para começar a vender.</p>
            </>
          ) : (
            <>
              <h2 className="text-2xl font-bold text-white">Verificação 2FA</h2>
              <p className="text-slate-400 text-sm mt-2">Digite o código do seu aplicativo autenticador.</p>
            </>
          )}
        </div>

        {showSupreme && (
          <div className="mb-6 flex justify-center">
            <span className="bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 px-4 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest flex items-center">
              <ShieldCheck size={12} className="mr-2" />
              Acesso Supremo Detectado
            </span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {step === 'credentials' ? (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-400 uppercase tracking-wider ml-1">E-mail</label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
                  <input 
                    ref={emailRef}
                    onChange={handleEmailChange}
                    type="email" 
                    className="w-full bg-slate-900/50 border border-slate-800 rounded-2xl py-3.5 pl-12 pr-4 text-white placeholder:text-slate-600 outline-none transition-all input-focus"
                    placeholder="seu@email.com"
                    autoComplete="email"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between items-center px-1">
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">Senha</label>
                  <a href="#" className="text-xs text-brand-500 hover:text-brand-400 font-medium">Esqueceu?</a>
                </div>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
                  <input 
                    ref={passwordRef}
                    type="password" 
                    className="w-full bg-slate-900/50 border border-slate-800 rounded-2xl py-3.5 pl-12 pr-4 text-white placeholder:text-slate-600 outline-none transition-all input-focus"
                    placeholder="••••••••"
                    autoComplete="current-password"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-1.5 text-center">
                <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">Código de 6 dígitos</label>
                <input 
                  ref={totpRef}
                  onChange={handleTotpChange}
                  type="text" 
                  inputMode="numeric"
                  className="w-full bg-slate-900/50 border border-slate-800 rounded-2xl py-4 px-4 text-center text-3xl font-mono tracking-[0.5em] text-white outline-none transition-all input-focus"
                  placeholder="000000"
                  autoFocus
                />
              </div>
              <button 
                type="button" 
                onClick={() => setStep('credentials')}
                className="w-full flex items-center justify-center text-sm text-slate-500 hover:text-white transition-colors"
              >
                <ChevronLeft size={16} className="mr-1" /> Voltar para o e-mail
              </button>
            </div>
          )}

          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-brand-500 hover:bg-brand-600 disabled:bg-slate-800 disabled:text-slate-600 text-white py-4 rounded-2xl font-bold flex items-center justify-center transition-all group active:scale-95 shadow-xl shadow-brand-500/20"
          >
            {loading ? (
              <Loader2 className="animate-spin" size={20} />
            ) : (
              <>
                {step === 'credentials' ? 'Entrar Agora' : 'Verificar e Entrar'}
                <ArrowRight size={18} className="ml-2 group-hover:translate-x-1 transition-transform" />
              </>
            )}
          </button>
        </form>

        <div className="mt-8 text-center text-sm">
          <span className="text-slate-500">Não tem uma conta?</span>
          <Link to="/" className="ml-1 text-brand-500 hover:text-brand-400 font-bold">Falar com vendas</Link>
        </div>
      </div>

      {/* Footer info */}
      <div className="absolute bottom-8 text-slate-600 text-[10px] uppercase tracking-widest flex items-center space-x-4">
        <span>© 2025 VoxFlow Inc.</span>
        <span>•</span>
        <span>Secure Session Active</span>
      </div>
    </div>
  )
}
