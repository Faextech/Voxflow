import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { PhoneCall, Menu, X, ArrowRight, CheckCircle2, PhoneForwarded, LayoutDashboard, Users, RotateCcw, Laptop, TrendingUp, Upload, Settings, Check, Quote, Star, ChevronDown, Timer, PhoneOff, EyeOff, MessageCircle, Heart, Phone } from 'lucide-react'

export default function Landing() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [planoAnual, setPlanoAnual] = useState(false)

  // Intersection Observer for scroll animations
  useEffect(() => {
    const observerOptions = { root: null, rootMargin: '0px', threshold: 0.1 }
    const observer = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible')
          observer.unobserve(entry.target)
        }
      })
    }, observerOptions)

    document.querySelectorAll('.fade-up').forEach(el => observer.observe(el))
    
    const handleScroll = () => {
      const header = document.querySelector('header')
      if (header) {
        if (window.scrollY > 10) header.classList.add('shadow-md')
        else header.classList.remove('shadow-md')
      }
    }
    window.addEventListener('scroll', handleScroll)
    return () => {
      window.removeEventListener('scroll', handleScroll)
      observer.disconnect()
    }
  }, [])

  return (
    <div className="text-slate-800 bg-white" style={{ fontFamily: 'Inter, sans-serif' }}>
      <style>{`
        .glass-header {
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .hero-gradient { background: linear-gradient(135deg, #0f1f5c 0%, #1e3a8a 100%); }
        .fade-up { opacity: 0; transform: translateY(30px); transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1); }
        .fade-up.visible { opacity: 1; transform: translateY(0); }
        .mockup-bar { width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-right: 6px; }
        .pulse-dot {
            width: 8px; height: 8px; border-radius: 50%; background-color: #22c55e;
            box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
            animation: pulse-ring 2s infinite;
        }
        @keyframes pulse-ring {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
        }
        .typing-effect {
            overflow: hidden; white-space: nowrap; border-right: 2px solid white;
            animation: typing 2s steps(20, end) infinite alternate;
        }
        @keyframes typing { from { width: 0 } to { width: 100% } }
      `}</style>

      {/* HEADER FIXO */}
      <header className="fixed w-full top-0 z-50 glass-header transition-all duration-300">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex justify-between items-center h-20">
                  <div className="flex-shrink-0 flex items-center cursor-pointer" onClick={() => window.scrollTo(0,0)}>
                      <PhoneCall className="h-7 w-7 text-navy-800 mr-2" />
                      <span className="font-extrabold text-2xl text-navy-900 tracking-tight">VoxFlow</span>
                  </div>
                  
                  <nav className="hidden md:flex space-x-8">
                      <a href="#funcionalidades" className="text-slate-600 hover:text-navy-800 font-medium transition-colors">Funcionalidades</a>
                      <a href="#como-funciona" className="text-slate-600 hover:text-navy-800 font-medium transition-colors">Como funciona</a>
                      <a href="#planos" className="text-slate-600 hover:text-navy-800 font-medium transition-colors">Planos</a>
                      <a href="#depoimentos" className="text-slate-600 hover:text-navy-800 font-medium transition-colors">Depoimentos</a>
                  </nav>

                  <div className="hidden md:flex items-center space-x-3">
                      <Link to="/login" className="text-slate-600 font-medium hover:text-navy-800 px-3 py-2 transition-colors">Entrar</Link>
                      <a href="https://wa.me/5500000000000" target="_blank" rel="noreferrer" className="text-slate-700 font-medium hover:text-navy-800 px-3 py-2 border border-slate-300 rounded-lg hover:border-slate-400 transition-all">Falar com consultor</a>
                      <Link to="/login" className="bg-brand-500 hover:bg-brand-600 text-white font-semibold px-5 py-2.5 rounded-lg shadow-soft transition-all hover:shadow-glow">Começar agora</Link>
                  </div>

                  <div className="md:hidden flex items-center">
                      <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="text-slate-600 hover:text-navy-900 focus:outline-none">
                          {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
                      </button>
                  </div>
              </div>
          </div>

          {/* Mobile Menu */}
          {mobileMenuOpen && (
            <div className="md:hidden bg-white border-b border-slate-100 shadow-xl absolute w-full transition-all">
                <div className="px-4 pt-2 pb-6 space-y-1">
                    <a href="#funcionalidades" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-3 text-base font-medium text-slate-700 hover:text-navy-800 hover:bg-slate-50 rounded-md">Funcionalidades</a>
                    <a href="#como-funciona" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-3 text-base font-medium text-slate-700 hover:text-navy-800 hover:bg-slate-50 rounded-md">Como funciona</a>
                    <a href="#planos" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-3 text-base font-medium text-slate-700 hover:text-navy-800 hover:bg-slate-50 rounded-md">Planos</a>
                    <a href="#depoimentos" onClick={() => setMobileMenuOpen(false)} className="block px-3 py-3 text-base font-medium text-slate-700 hover:text-navy-800 hover:bg-slate-50 rounded-md">Depoimentos</a>
                    <div className="pt-4 flex flex-col space-y-3 px-3">
                        <Link to="/login" className="text-center text-slate-700 font-medium px-4 py-2 bg-slate-100 rounded-lg">Entrar na minha conta</Link>
                        <a href="https://wa.me/5500000000000" target="_blank" rel="noreferrer" className="text-center text-slate-700 font-medium px-4 py-3 border border-slate-300 rounded-lg">Falar com consultor</a>
                        <Link to="/login" className="text-center bg-brand-500 text-white font-semibold px-4 py-3 rounded-lg">Começar agora</Link>
                    </div>
                </div>
            </div>
          )}
      </header>

      {/* HERO */}
      <section className="hero-gradient pt-28 pb-14 lg:pt-40 lg:pb-28 overflow-hidden relative">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
              <div className="flex flex-col lg:grid lg:grid-cols-12 lg:gap-16 items-center">
                  <div className="lg:col-span-6 text-center lg:text-left fade-up">
                      <div className="inline-flex items-center px-3 py-1 rounded-full bg-white/10 border border-white/20 text-white text-sm font-medium mb-6">
                          <span className="text-green-500 mr-2 text-lg leading-none">✦</span> Novo — Discagem automática com IA
                      </div>
                      <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold text-white tracking-tight mb-4 md:mb-6 leading-[1.1]">
                          Sua equipe vende mais. <span className="text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-300">Sem esforço manual.</span>
                      </h1>
                      <p className="text-base md:text-xl text-indigo-100 opacity-90 mb-8 md:mb-10 max-w-2xl mx-auto lg:mx-0 leading-relaxed">
                          Automatize sua operação de vendas e deixe sua equipe focada no que realmente importa: fechar negócios e aumentar a receita.
                      </p>
                      <div className="flex flex-col sm:flex-row gap-3 md:gap-4 justify-center lg:justify-start mb-8 md:mb-12">
                          <a href="https://wa.me/5500000000000" target="_blank" rel="noreferrer" className="w-full sm:w-auto inline-flex justify-center items-center px-8 py-4 border border-transparent text-base md:text-lg font-semibold rounded-xl text-white bg-brand-500 hover:bg-brand-600 shadow-glow transition-all hover:-translate-y-1">
                              Quero uma demonstração
                          </a>
                          <a href="#como-funciona" className="w-full sm:w-auto inline-flex justify-center items-center px-8 py-4 border border-white/30 text-base md:text-lg font-semibold rounded-xl text-white hover:bg-white/10 transition-all">
                              Ver como funciona ↓
                          </a>
                      </div>
                      
                      <div className="grid grid-cols-3 lg:flex lg:items-center lg:justify-start lg:gap-6 gap-2 text-white border-t border-white/20 pt-6 md:pt-8">
                          <div className="text-center lg:text-left">
                              <div className="text-xl md:text-2xl font-bold">200+</div>
                              <div className="text-xs md:text-sm text-indigo-200">Empresas</div>
                          </div>
                          <div className="hidden lg:block w-px h-10 bg-white/20"></div>
                          <div className="text-center lg:text-left">
                              <div className="text-xl md:text-2xl font-bold">1M+</div>
                              <div className="text-xs md:text-sm text-indigo-200">Ligações/mês</div>
                          </div>
                          <div className="hidden lg:block w-px h-10 bg-white/20"></div>
                          <div className="text-center lg:text-left">
                              <div className="text-xl md:text-2xl font-bold flex items-center justify-center lg:justify-start">4.9 <Star className="h-4 w-4 md:h-5 md:w-5 fill-current text-yellow-400 ml-1" /></div>
                              <div className="text-xs md:text-sm text-indigo-200">Avaliação</div>
                          </div>
                      </div>
                  </div>

                  <div className="lg:col-span-6 mt-10 lg:mt-0 fade-up w-full">
                      <div className="bg-slate-900 rounded-2xl border border-slate-700 shadow-2xl overflow-hidden relative transform rotate-1 hover:rotate-0 transition-transform duration-500">
                          <div className="bg-slate-800 px-3 md:px-4 py-2 md:py-3 flex items-center border-b border-slate-700">
                              <div className="flex gap-1.5 md:gap-2">
                                  <div className="mockup-bar bg-red-500"></div>
                                  <div className="mockup-bar bg-yellow-500"></div>
                                  <div className="mockup-bar bg-green-500"></div>
                              </div>
                              <div className="mx-auto text-xs text-slate-400 font-mono">app.voxflow.com.br</div>
                          </div>
                          <div className="p-3 md:p-6">
                              <div className="grid grid-cols-3 gap-2 md:gap-4 mb-3 md:mb-6">
                                  <div className="bg-slate-800 p-2 md:p-4 rounded-lg md:rounded-xl border border-slate-700">
                                      <div className="text-slate-400 text-[10px] md:text-xs mb-0.5 md:mb-1 uppercase tracking-wider">Ligações Hoje</div>
                                      <div className="text-white font-bold text-base md:text-2xl">1.432</div>
                                  </div>
                                  <div className="bg-slate-800 p-2 md:p-4 rounded-lg md:rounded-xl border border-slate-700">
                                      <div className="text-slate-400 text-[10px] md:text-xs mb-0.5 md:mb-1 uppercase tracking-wider">Taxa de Contato</div>
                                      <div className="text-green-500 font-bold text-base md:text-2xl">42%</div>
                                  </div>
                                  <div className="bg-slate-800 p-2 md:p-4 rounded-lg md:rounded-xl border border-slate-700 flex justify-between items-center">
                                      <div>
                                          <div className="text-slate-400 text-[10px] md:text-xs mb-0.5 md:mb-1 uppercase tracking-wider">Em Espera</div>
                                          <div className="text-white font-bold text-base md:text-2xl">8</div>
                                      </div>
                                      <div className="pulse-dot"></div>
                                  </div>
                              </div>

                              <div className="bg-gradient-to-r from-indigo-600 to-indigo-500 rounded-xl p-3 md:p-5 mb-3 md:mb-6 text-white shadow-glow relative overflow-hidden">
                                  <div className="absolute right-0 top-0 opacity-10">
                                      <Phone className="h-20 w-20 md:h-32 md:w-32 -mt-4 -mr-4" />
                                  </div>
                                  <div className="flex items-center gap-3 md:gap-4 relative z-10">
                                      <div className="h-9 w-9 md:h-12 md:w-12 rounded-full bg-white/20 flex items-center justify-center shrink-0">
                                          <Users className="h-5 w-5 md:h-6 md:w-6" />
                                      </div>
                                      <div className="min-w-0">
                                          <div className="text-xs md:text-sm text-green-100 font-medium">Chamada Atendida</div>
                                          <div className="font-bold text-sm md:text-xl typing-effect">João Silva — TechCorp</div>
                                      </div>
                                  </div>
                              </div>

                              <div className="bg-slate-800 rounded-xl border border-slate-700">
                                  <div className="px-3 md:px-4 py-2 md:py-3 border-b border-slate-700 flex justify-between text-[10px] md:text-xs text-slate-400 font-semibold uppercase">
                                      <span>Operador</span>
                                      <span>Status</span>
                                  </div>
                                  <div className="px-3 md:px-4 py-2 md:py-3 border-b border-slate-700 flex justify-between items-center">
                                      <div className="flex items-center gap-2 md:gap-3 text-white text-xs md:text-sm"><div className="h-5 w-5 md:h-6 md:w-6 rounded-full bg-blue-500 text-[10px] md:text-xs flex items-center justify-center shrink-0">AM</div> Aline M.</div>
                                      <span className="text-[10px] md:text-xs px-1.5 md:px-2 py-0.5 md:py-1 bg-green-500/20 text-green-400 rounded-md flex items-center gap-1"><div className="pulse-dot w-1.5 h-1.5"></div> Em chamada</span>
                                  </div>
                                  <div className="px-3 md:px-4 py-2 md:py-3 flex justify-between items-center">
                                      <div className="flex items-center gap-2 md:gap-3 text-white text-xs md:text-sm"><div className="h-5 w-5 md:h-6 md:w-6 rounded-full bg-purple-500 text-[10px] md:text-xs flex items-center justify-center shrink-0">CR</div> Carlos R.</div>
                                      <span className="text-[10px] md:text-xs px-1.5 md:px-2 py-0.5 md:py-1 bg-yellow-500/20 text-yellow-400 rounded-md">Pausado</span>
                                  </div>
                              </div>
                          </div>
                      </div>
                  </div>
              </div>
          </div>
          
          <div className="absolute bottom-0 left-0 right-0 z-0">
              <svg viewBox="0 0 1440 120" className="w-full h-auto text-slate-50 fill-current" preserveAspectRatio="none">
                  <path d="M0,64L80,69.3C160,75,320,85,480,80C640,75,800,53,960,48C1120,43,1280,53,1360,58.7L1440,64L1440,120L1360,120C1280,120,1120,120,960,120C800,120,640,120,480,120C320,120,160,120,80,120L0,120Z"></path>
              </svg>
          </div>
      </section>

      {/* DOR → SOLUÇÃO */}
      <section className="py-24 bg-slate-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="text-center max-w-3xl mx-auto mb-16 fade-up">
                  <h2 className="text-3xl md:text-4xl font-extrabold text-navy-900 mb-4">Sua equipe está perdendo tempo</h2>
                  <p className="text-lg text-slate-600">O processo manual de discagem custa horas do dia dos seus vendedores. Nós resolvemos isso.</p>
              </div>

              <div className="grid md:grid-cols-3 gap-8">
                  <div className="bg-white rounded-2xl p-5 md:p-8 shadow-soft border border-slate-100 border-l-4 border-l-red-500 fade-up hover:-translate-y-2 transition-transform">
                      <div className="w-14 h-14 bg-red-50 text-red-500 rounded-xl flex items-center justify-center mb-6">
                          <Timer className="h-7 w-7" />
                      </div>
                      <h3 className="text-xl font-bold text-slate-800 mb-3">40% do dia discando manualmente</h3>
                      <p className="text-slate-500 mb-4">Ouvindo caixa postal, número inexistente e chamadas não atendidas.</p>
                      <div className="pt-4 border-t border-slate-100">
                          <div className="text-brand-500 font-semibold flex items-center">
                              <CheckCircle2 className="h-5 w-5 mr-2" /> Discagem automática contínua
                          </div>
                      </div>
                  </div>

                  <div className="bg-white rounded-2xl p-5 md:p-8 shadow-soft border border-slate-100 border-l-4 border-l-blue-500 fade-up hover:-translate-y-2 transition-transform" style={{ transitionDelay: '100ms' }}>
                      <div className="w-14 h-14 bg-blue-50 text-blue-500 rounded-xl flex items-center justify-center mb-6">
                          <PhoneOff className="h-7 w-7" />
                      </div>
                      <h3 className="text-xl font-bold text-slate-800 mb-3">Leads sem follow-up esfriando</h3>
                      <p className="text-slate-500 mb-4">Vendedores esquecem de retornar as ligações ou perdem o timing ideal.</p>
                      <div className="pt-4 border-t border-slate-100">
                          <div className="text-brand-500 font-semibold flex items-center">
                              <CheckCircle2 className="h-5 w-5 mr-2" /> Fila inteligente de retorno
                          </div>
                      </div>
                  </div>

                  <div className="bg-white rounded-2xl p-5 md:p-8 shadow-soft border border-slate-100 border-l-4 border-l-purple-500 fade-up hover:-translate-y-2 transition-transform" style={{ transitionDelay: '200ms' }}>
                      <div className="w-14 h-14 bg-purple-50 text-purple-500 rounded-xl flex items-center justify-center mb-6">
                          <EyeOff className="h-7 w-7" />
                      </div>
                      <h3 className="text-xl font-bold text-slate-800 mb-3">Sem visibilidade da operação</h3>
                      <p className="text-slate-500 mb-4">Gestores não sabem quem está produzindo ou por que as vendas caíram.</p>
                      <div className="pt-4 border-t border-slate-100">
                          <div className="text-brand-500 font-semibold flex items-center">
                              <CheckCircle2 className="h-5 w-5 mr-2" /> Dashboard ao vivo
                          </div>
                      </div>
                  </div>
              </div>
          </div>
      </section>

      {/* FUNCIONALIDADES */}
      <section id="funcionalidades" className="py-24 bg-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="text-center max-w-3xl mx-auto mb-16 fade-up">
                  <h2 className="text-3xl md:text-4xl font-extrabold text-navy-900 mb-4">Tudo que sua operação precisa</h2>
                  <p className="text-lg text-slate-600">Uma plataforma unificada. Do primeiro contato ao fechamento do negócio.</p>
              </div>

              <div className="grid md:grid-cols-3 gap-8">
                  {[
                      { icon: PhoneForwarded, color: 'text-indigo-600', bg: 'bg-indigo-50', title: 'Discagem Automática', desc: 'Filtra caixas postais e ocupados, conectando o operador apenas quando o cliente atende.' },
                      { icon: LayoutDashboard, color: 'text-blue-600', bg: 'bg-blue-50', title: 'Dashboard em Tempo Real', desc: 'Monitore todos os operadores, ligações ativas e métricas vitais em uma única tela.' },
                      { icon: Users, color: 'text-brand-500', bg: 'bg-green-50', title: 'Gestão de Leads', desc: 'Importação fácil, funil de vendas integrado e histórico completo de cada contato.' },
                      { icon: RotateCcw, color: 'text-orange-600', bg: 'bg-orange-50', title: 'Retorno Automático', desc: 'O sistema agenda retornos automaticamente e joga o lead na fila no momento exato.' },
                      { icon: Laptop, color: 'text-purple-600', bg: 'bg-purple-50', title: 'Softphone no Navegador', desc: 'Sem instalar nada. A ligação acontece pelo próprio navegador com alta qualidade de áudio.' },
                      { icon: TrendingUp, color: 'text-rose-600', bg: 'bg-rose-50', title: 'Relatórios Detalhados', desc: 'Meça o desempenho de cada campanha, conversões e produtividade individual da equipe.' }
                  ].map((feat, i) => (
                      <div key={i} className="group p-5 md:p-8 rounded-2xl border border-slate-200 hover:border-green-500 hover:shadow-xl transition-all bg-white fade-up" style={{ transitionDelay: `${i * 50}ms` }}>
                          <div className={`w-12 h-12 ${feat.bg} ${feat.color} rounded-lg flex items-center justify-center mb-6 group-hover:scale-110 transition-transform`}>
                              <feat.icon className="h-6 w-6" />
                          </div>
                          <h3 className="text-xl font-bold text-slate-800 mb-3">{feat.title}</h3>
                          <p className="text-slate-600">{feat.desc}</p>
                      </div>
                  ))}
              </div>
          </div>
      </section>

      {/* PLANOS */}
      <section id="planos" className="py-24 bg-slate-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="text-center max-w-3xl mx-auto mb-12 fade-up">
                  <h2 className="text-3xl md:text-4xl font-extrabold text-navy-900 mb-4">Planos claros. Sem surpresas.</h2>
                  <p className="text-lg text-slate-600 mb-8">Mensalidade fixa. Cancele quando quiser.</p>
                  
                  <div className="flex items-center justify-center gap-4">
                      <span className={planoAnual ? 'text-slate-500' : 'text-slate-900 font-semibold'}>Mensal</span>
                      <button onClick={() => setPlanoAnual(!planoAnual)} className={`relative inline-flex h-7 w-14 items-center rounded-full transition-colors focus:outline-none ${planoAnual ? 'bg-brand-500' : 'bg-slate-300'}`}>
                          <span className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${planoAnual ? 'translate-x-8' : 'translate-x-1'}`}></span>
                      </button>
                      <span className={planoAnual ? 'text-slate-900 font-semibold' : 'text-slate-500'}>Anual <span className="text-xs text-brand-600 bg-green-100 px-2 py-0.5 rounded-full ml-1">15% off</span></span>
                  </div>
              </div>

              <div className="grid lg:grid-cols-3 gap-8 max-w-6xl mx-auto items-center">
                  {/* STARTER */}
                  <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-soft fade-up">
                      <h3 className="text-xl font-bold text-slate-800 mb-2">Starter</h3>
                      <p className="text-slate-500 text-sm mb-6">Para pequenas equipes começando a estruturar a operação.</p>
                      <div className="mb-8">
                          <span className="text-4xl font-extrabold text-navy-900">R$ {planoAnual ? '507' : '597'}</span><span className="text-slate-500">/mês</span>
                      </div>
                      <ul className="space-y-4 mb-8">
                          {['Até 5 operadores', 'Discagem automática', 'Dashboard básico', 'Gestão de leads', 'Suporte por chat'].map((f, i) => (
                              <li key={i} className="flex items-center text-slate-600"><Check className="h-5 w-5 text-green-500 mr-3 shrink-0" /> {f}</li>
                          ))}
                      </ul>
                      <a href="https://wa.me/5500000000000" target="_blank" rel="noreferrer" className="block w-full py-3 px-4 border-2 border-brand-500 text-brand-500 font-bold rounded-xl text-center hover:bg-green-50 transition-colors">Falar com consultor</a>
                  </div>

                  {/* PRO */}
                  <div className="bg-navy-900 rounded-3xl p-8 border border-green-500 shadow-2xl transform lg:scale-105 relative z-10 fade-up">
                      <div className="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
                          <span className="bg-brand-500 text-white text-xs font-bold uppercase tracking-wider py-1 px-3 rounded-full">Mais popular</span>
                      </div>
                      <h3 className="text-xl font-bold text-white mb-2">Pro</h3>
                      <p className="text-indigo-200 text-sm mb-6">A solução completa para escalar suas vendas com força total.</p>
                      <div className="mb-8">
                          <span className="text-4xl font-extrabold text-white">R$ {planoAnual ? '1.102' : '1.297'}</span><span className="text-indigo-200">/mês</span>
                      </div>
                      <ul className="space-y-4 mb-8">
                          {['Até 20 operadores', 'Discagem avançada', 'CRM com pipeline', 'Relatórios por operador', 'Retorno automático', 'Suporte prioritário'].map((f, i) => (
                              <li key={i} className="flex items-center text-indigo-50"><Check className="h-5 w-5 text-green-400 mr-3 shrink-0" /> {f}</li>
                          ))}
                      </ul>
                      <a href="https://wa.me/5500000000000" target="_blank" rel="noreferrer" className="block w-full py-3 px-4 bg-brand-500 text-white font-bold rounded-xl text-center hover:bg-brand-600 transition-colors shadow-glow">Falar com consultor</a>
                  </div>

                  {/* ENTERPRISE */}
                  <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-soft fade-up">
                      <h3 className="text-xl font-bold text-slate-800 mb-2">Enterprise</h3>
                      <p className="text-slate-500 text-sm mb-6">Operações gigantes que precisam de integrações exclusivas.</p>
                      <div className="mb-8">
                          <span className="text-4xl font-extrabold text-navy-900">Personalizado</span>
                      </div>
                      <ul className="space-y-4 mb-8">
                          {['Operadores ilimitados', 'Multi-campanhas', 'API e integrações personalizadas', 'Gerente dedicado (CSM)', 'SLA garantido'].map((f, i) => (
                              <li key={i} className="flex items-center text-slate-600"><Check className="h-5 w-5 text-slate-400 mr-3 shrink-0" /> {f}</li>
                          ))}
                      </ul>
                      <a href="https://wa.me/5500000000000" target="_blank" rel="noreferrer" className="block w-full py-3 px-4 border border-slate-300 text-slate-700 font-bold rounded-xl text-center hover:bg-slate-50 transition-colors">Falar com consultor</a>
                  </div>
              </div>
          </div>
      </section>

      {/* FOOTER */}
      <footer className="bg-slate-900 border-t border-slate-800 pt-16 pb-8">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12 mb-12">
                  <div className="col-span-2 md:col-span-1">
                      <div className="flex items-center mb-4 justify-center md:justify-start">
                          <PhoneCall className="h-6 w-6 text-green-500 mr-2" />
                          <span className="font-bold text-xl text-white tracking-tight">VoxFlow</span>
                      </div>
                      <p className="text-slate-400 text-sm mb-6 max-w-xs text-center md:text-left mx-auto md:mx-0">Mais ligações. Mais vendas. Menos esforço. O motor inteligente da sua equipe de vendas.</p>
                      <div className="flex space-x-4 justify-center md:justify-start">
                          <a href="https://wa.me/5500000000000" className="text-slate-400 hover:text-white transition-colors"><MessageCircle className="h-5 w-5" /></a>
                      </div>
                  </div>
                  
                  <div>
                      <h4 className="text-white font-semibold mb-4 uppercase text-xs tracking-wider">Produto</h4>
                      <ul className="space-y-3">
                          <li><a href="#funcionalidades" className="text-slate-400 hover:text-green-400 text-sm transition-colors">Funcionalidades</a></li>
                          <li><a href="#planos" className="text-slate-400 hover:text-green-400 text-sm transition-colors">Planos e Preços</a></li>
                      </ul>
                  </div>

                  <div>
                      <h4 className="text-white font-semibold mb-4 uppercase text-xs tracking-wider">Empresa</h4>
                      <ul className="space-y-3">
                          <li><a href="#" className="text-slate-400 hover:text-green-400 text-sm transition-colors">Sobre nós</a></li>
                          <li><a href="#depoimentos" className="text-slate-400 hover:text-green-400 text-sm transition-colors">Clientes</a></li>
                      </ul>
                  </div>

                  <div>
                      <h4 className="text-white font-semibold mb-4 uppercase text-xs tracking-wider">Legal</h4>
                      <ul className="space-y-3">
                          <li><a href="#" className="text-slate-400 hover:text-green-400 text-sm transition-colors">Termos de Serviço</a></li>
                          <li><a href="#" className="text-slate-400 hover:text-green-400 text-sm transition-colors">Privacidade</a></li>
                      </ul>
                  </div>
              </div>
              
              <div className="border-t border-slate-800 pt-8 flex flex-col md:flex-row justify-between items-center">
                  <p className="text-slate-500 text-sm">© 2025 VoxFlow. Todos os direitos reservados.</p>
                  <div className="mt-4 md:mt-0 text-slate-500 text-sm flex items-center">
                      Feito com <Heart className="h-4 w-4 text-red-500 mx-1 fill-current" /> no Brasil
                  </div>
              </div>
          </div>
      </footer>
    </div>
  )
}
