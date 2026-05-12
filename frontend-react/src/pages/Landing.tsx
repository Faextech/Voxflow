import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { 
  PhoneCall, Menu, X, CheckCircle2, PhoneForwarded, 
  LayoutDashboard, Users, RotateCcw, Laptop, TrendingUp, 
  Check, Star, Timer, PhoneOff, EyeOff, MessageCircle, 
  Heart, Phone, ArrowRight, Zap, Shield, BarChart3, Globe, Play
} from 'lucide-react'

export default function Landing() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', handleScroll)
    
    // Intersection Observer for animations
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('animate-in')
        }
      })
    }, { threshold: 0.1 })

    document.querySelectorAll('.reveal').forEach(el => observer.observe(el))
    
    return () => {
      window.removeEventListener('scroll', handleScroll)
      observer.disconnect()
    }
  }, [])

  return (
    <div className="min-h-screen text-slate-900 bg-white selection:bg-brand-500/30 selection:text-brand-900" style={{ fontFamily: "'Inter', sans-serif" }}>
      <style>{`
        @keyframes blob {
          0% { transform: translate(0px, 0px) scale(1); }
          33% { transform: translate(30px, -50px) scale(1.1); }
          66% { transform: translate(-20px, 20px) scale(0.9); }
          100% { transform: translate(0px, 0px) scale(1); }
        }
        .animate-blob { animation: blob 7s infinite; }
        .animation-delay-2000 { animation-delay: 2s; }
        .animation-delay-4000 { animation-delay: 4s; }
        
        .glass {
          background: rgba(255, 255, 255, 0.7);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .hero-gradient {
          background: radial-gradient(circle at top right, #1e3a8a, #0f172a);
        }
        
        .reveal { opacity: 0; transform: translateY(20px); transition: all 0.7s cubic-bezier(0.4, 0, 0.2, 1); }
        .reveal.animate-in { opacity: 1; transform: translateY(0); }
        
        .shadow-glow { box-shadow: 0 0 20px rgba(22, 163, 74, 0.3); }
        .shadow-glow-blue { box-shadow: 0 0 20px rgba(59, 130, 246, 0.3); }

        .mockup-card {
          background: rgba(15, 23, 42, 0.9);
          border: 1px solid rgba(255, 255, 255, 0.1);
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }

        .pulse-green {
          box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4);
          animation: pulse-green 2s infinite;
        }
        @keyframes pulse-green {
          0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
          70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(34, 197, 94, 0); }
          100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
        }

        .text-gradient {
          background: linear-gradient(to right, #4ade80, #2dd4bf);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
      `}</style>

      {/* NAVIGATION */}
      <nav className={`fixed top-0 w-full z-50 transition-all duration-300 ${scrolled ? 'glass py-3 shadow-lg' : 'bg-transparent py-5'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex justify-between items-center">
          <div className="flex items-center space-x-2 group cursor-pointer" onClick={() => window.scrollTo({top: 0, behavior: 'smooth'})}>
            <div className="bg-brand-500 p-2 rounded-xl group-hover:rotate-12 transition-transform shadow-lg shadow-brand-500/20">
              <PhoneCall className="h-6 w-6 text-white" />
            </div>
            <span className={`text-2xl font-bold tracking-tight ${scrolled ? 'text-slate-900' : 'text-white'}`}>VoxFlow</span>
          </div>

          <div className="hidden md:flex items-center space-x-8">
            <a href="#funcionalidades" className={`text-sm font-medium transition-colors ${scrolled ? 'text-slate-600 hover:text-brand-600' : 'text-white/80 hover:text-white'}`}>Funcionalidades</a>
            <a href="#como-funciona" className={`text-sm font-medium transition-colors ${scrolled ? 'text-slate-600 hover:text-brand-600' : 'text-white/80 hover:text-white'}`}>Como funciona</a>
            <a href="#planos" className={`text-sm font-medium transition-colors ${scrolled ? 'text-slate-600 hover:text-brand-600' : 'text-white/80 hover:text-white'}`}>Preços</a>
            <div className="h-6 w-px bg-slate-300/30"></div>
            <Link to="/login" className={`text-sm font-medium transition-colors ${scrolled ? 'text-slate-600 hover:text-brand-600' : 'text-white/80 hover:text-white'}`}>Entrar</Link>
            <Link to="/login" className="bg-brand-500 hover:bg-brand-600 text-white px-6 py-2.5 rounded-full font-semibold shadow-lg shadow-brand-500/20 transition-all hover:scale-105 active:scale-95">
              Começar Grátis
            </Link>
          </div>

          <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className={`md:hidden p-2 rounded-lg ${scrolled ? 'text-slate-900 hover:bg-slate-100' : 'text-white hover:bg-white/10'}`}>
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* MOBILE MENU */}
        {mobileMenuOpen && (
          <div className="md:hidden absolute top-full left-0 w-full glass shadow-2xl border-t border-slate-200/50 p-4 space-y-2 animate-in slide-in-from-top-4 duration-200">
            <a href="#funcionalidades" onClick={() => setMobileMenuOpen(false)} className="block px-4 py-3 rounded-xl hover:bg-slate-100 font-medium text-slate-700">Funcionalidades</a>
            <a href="#como-funciona" onClick={() => setMobileMenuOpen(false)} className="block px-4 py-3 rounded-xl hover:bg-slate-100 font-medium text-slate-700">Como funciona</a>
            <a href="#planos" onClick={() => setMobileMenuOpen(false)} className="block px-4 py-3 rounded-xl hover:bg-slate-100 font-medium text-slate-700">Planos</a>
            <div className="pt-2 border-t border-slate-200 space-y-2">
              <Link to="/login" className="block px-4 py-3 rounded-xl text-center font-bold text-slate-700 bg-slate-100">Entrar</Link>
              <Link to="/login" className="block px-4 py-3 rounded-xl text-center font-bold text-white bg-brand-500">Começar Grátis</Link>
            </div>
          </div>
        )}
      </nav>

      {/* HERO SECTION */}
      <main className="relative hero-gradient pt-32 pb-20 lg:pt-52 lg:pb-40 overflow-hidden">
        {/* Animated Background Blobs */}
        <div className="absolute top-0 -left-4 w-72 h-72 bg-brand-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
        <div className="absolute top-0 -right-4 w-72 h-72 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-8 left-20 w-72 h-72 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="lg:flex lg:items-center lg:space-x-12">
            <div className="lg:w-1/2 reveal">
              <div className="inline-flex items-center space-x-2 bg-white/10 border border-white/20 px-3 py-1.5 rounded-full mb-8">
                <span className="flex h-2 w-2 rounded-full bg-brand-400 animate-pulse"></span>
                <span className="text-white text-xs font-semibold tracking-wide uppercase">Novo: Discador Preditivo 2.0</span>
              </div>
              
              <h1 className="text-5xl lg:text-7xl font-extrabold text-white leading-tight mb-8">
                Sua equipe vende mais. <br />
                <span className="text-gradient">Sem esforço manual.</span>
              </h1>
              
              <p className="text-xl text-white/70 mb-10 max-w-xl leading-relaxed">
                Aumente em até 300% a produtividade do seu call center com discagem automática, IA e gestão de leads em tempo real.
              </p>

              <div className="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4 mb-12">
                <Link to="/login" className="group flex items-center justify-center bg-brand-500 hover:bg-brand-600 text-white px-8 py-4 rounded-2xl font-bold text-lg shadow-xl shadow-brand-500/30 transition-all hover:-translate-y-1">
                  Quero Demonstração Gratuita
                  <ArrowRight size={20} className="ml-2 group-hover:translate-x-1 transition-transform" />
                </Link>
                <a href="#como-funciona" className="flex items-center justify-center bg-white/10 hover:bg-white/20 text-white px-8 py-4 rounded-2xl font-bold text-lg border border-white/20 transition-all">
                  <Play size={20} className="mr-2 fill-current" />
                  Ver como funciona
                </a>
              </div>

              <div className="flex items-center space-x-6 text-white/50">
                <div className="flex -space-x-2">
                  {[1,2,3,4].map(i => (
                    <div key={i} className="w-10 h-10 rounded-full border-2 border-slate-900 bg-slate-800 flex items-center justify-center text-xs font-bold text-white">
                      U{i}
                    </div>
                  ))}
                </div>
                <p className="text-sm">
                  <span className="text-white font-bold">+200 empresas</span> já escalando com VoxFlow
                </p>
              </div>
            </div>

            <div className="lg:w-1/2 mt-20 lg:mt-0 reveal transition-all duration-1000 delay-300">
              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-brand-500 to-blue-500 rounded-3xl blur opacity-25 group-hover:opacity-40 transition duration-1000"></div>
                <div className="relative mockup-card rounded-3xl overflow-hidden shadow-2xl">
                  {/* Mockup Header */}
                  <div className="bg-slate-800/80 px-6 py-4 flex items-center justify-between border-b border-white/5">
                    <div className="flex space-x-1.5">
                      <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
                      <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
                      <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
                    </div>
                    <div className="text-[10px] font-mono text-white/30 tracking-widest uppercase">Dashboard.Voxflow.v4</div>
                    <div className="w-8"></div>
                  </div>
                  
                  {/* Mockup Content */}
                  <div className="p-8 space-y-8">
                    <div className="grid grid-cols-3 gap-6">
                      <div className="bg-white/5 p-4 rounded-2xl border border-white/5">
                        <div className="text-white/40 text-[10px] font-bold uppercase tracking-wider mb-2">Ligações Hoje</div>
                        <div className="text-2xl font-bold text-white">1.842</div>
                        <div className="text-brand-400 text-xs mt-1 flex items-center">
                          <TrendingUp size={12} className="mr-1" /> +12.4%
                        </div>
                      </div>
                      <div className="bg-white/5 p-4 rounded-2xl border border-white/5">
                        <div className="text-white/40 text-[10px] font-bold uppercase tracking-wider mb-2">Contatos</div>
                        <div className="text-2xl font-bold text-white">42%</div>
                        <div className="text-blue-400 text-xs mt-1">Acima da média</div>
                      </div>
                      <div className="bg-white/5 p-4 rounded-2xl border border-white/5">
                        <div className="text-white/40 text-[10px] font-bold uppercase tracking-wider mb-2">Em Espera</div>
                        <div className="text-2xl font-bold text-white">0</div>
                        <div className="text-green-400 text-xs mt-1 flex items-center">
                          <CheckCircle2 size={12} className="mr-1" /> Fila limpa
                        </div>
                      </div>
                    </div>

                    <div className="bg-brand-500/20 border border-brand-500/30 rounded-2xl p-6 relative overflow-hidden group/call">
                      <div className="absolute top-0 right-0 p-4 opacity-10">
                        <Phone size={80} />
                      </div>
                      <div className="flex items-center space-x-4 relative z-10">
                        <div className="w-12 h-12 rounded-full bg-brand-500 flex items-center justify-center pulse-green shadow-lg shadow-brand-500/50">
                          <PhoneForwarded className="text-white" size={24} />
                        </div>
                        <div>
                          <div className="text-brand-400 text-xs font-bold uppercase tracking-wider">Chamada em Progresso</div>
                          <div className="text-xl font-bold text-white">João Silva — Tech Solutions</div>
                          <div className="text-white/40 text-sm mt-1">Duração: 02:45 • Campanha: Outbound SP</div>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                        <div className="h-full bg-brand-500 w-3/4 rounded-full"></div>
                      </div>
                      <div className="flex justify-between text-[10px] font-bold text-white/30 uppercase tracking-widest">
                        <span>Meta Diária</span>
                        <span>75% Concluído</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        {/* WAVE SEPARATOR */}
        <div className="absolute bottom-0 left-0 w-full overflow-hidden leading-none rotate-180">
          <svg viewBox="0 0 1200 120" preserveAspectRatio="none" className="relative block w-full h-[60px] fill-white">
            <path d="M321.39,56.44c58-10.79,114.16-30.13,172-41.86,82.39-16.72,168.19-17.73,250.45-.39C823.78,31,906.67,72,985.66,92.83c70.05,18.48,146.53,26.09,214.34,3V0H0V120c64.12-24.52,143.52-19.13,210.47-15.03C251.65,108.57,285.34,64.21,321.39,56.44Z"></path>
          </svg>
        </div>
      </main>

      {/* STATS BAR */}
      <section className="bg-white py-12 border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <div className="text-center">
              <div className="text-4xl font-bold text-slate-900 mb-1">98%</div>
              <div className="text-slate-500 text-sm font-medium uppercase tracking-wider">Uptime</div>
            </div>
            <div className="text-center border-l border-slate-100">
              <div className="text-4xl font-bold text-slate-900 mb-1">3x</div>
              <div className="text-slate-500 text-sm font-medium uppercase tracking-wider">Conversão</div>
            </div>
            <div className="text-center border-l border-slate-100">
              <div className="text-4xl font-bold text-slate-900 mb-1">200+</div>
              <div className="text-slate-500 text-sm font-medium uppercase tracking-wider">Empresas</div>
            </div>
            <div className="text-center border-l border-slate-100">
              <div className="text-4xl font-bold text-slate-900 mb-1">24/7</div>
              <div className="text-slate-500 text-sm font-medium uppercase tracking-wider">Suporte</div>
            </div>
          </div>
        </div>
      </section>

      {/* FEATURES GRID */}
      <section id="funcionalidades" className="py-24 bg-slate-50 relative overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="text-center max-w-3xl mx-auto mb-20 reveal">
            <h2 className="text-brand-600 font-bold tracking-widest uppercase text-sm mb-4">Funcionalidades Elite</h2>
            <h3 className="text-4xl md:text-5xl font-extrabold text-slate-900 mb-6 leading-tight">Tudo que sua operação precisa para dominar o mercado</h3>
            <p className="text-lg text-slate-600">Elimine o trabalho manual e dê superpoderes à sua equipe com tecnologia de ponta.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                icon: <Zap size={24} className="text-brand-500" />,
                title: "Discador Automático",
                desc: "Filtra secretárias, caixa postal e números inválidos. Seu operador só fala com quem atende.",
                color: "bg-brand-50"
              },
              {
                icon: <BarChart3 size={24} className="text-blue-500" />,
                title: "Dashboard Realtime",
                desc: "Acompanhe cada ligação, métrica de conversão e status dos operadores em tempo real.",
                color: "bg-blue-50"
              },
              {
                icon: <Users size={24} className="text-purple-500" />,
                title: "CRM Integrado",
                desc: "Gestão completa de leads, histórico de chamadas e pipeline de vendas unificado.",
                color: "bg-purple-50"
              },
              {
                icon: <RotateCcw size={24} className="text-orange-500" />,
                title: "Retorno Automático",
                desc: "Agende retornos e deixe o sistema discar na hora certa. Nunca mais perca um follow-up.",
                color: "bg-orange-50"
              },
              {
                icon: <Laptop size={24} className="text-indigo-500" />,
                title: "Softphone Browser",
                desc: "Sem aparelhos. Sem cabos. Ligue direto do navegador com áudio HD de alta fidelidade.",
                color: "bg-indigo-50"
              },
              {
                icon: <Shield size={24} className="text-emerald-500" />,
                title: "Gestão de DNC",
                desc: "Bloqueio automático de números 'Não Perturbe' e conformidade total com a LGPD.",
                color: "bg-emerald-50"
              }
            ].map((f, i) => (
              <div key={i} className="bg-white p-10 rounded-3xl border border-slate-200 hover:border-brand-500/50 hover:shadow-2xl hover:shadow-brand-500/10 transition-all duration-300 group reveal">
                <div className={`${f.color} w-14 h-14 rounded-2xl flex items-center justify-center mb-8 group-hover:scale-110 transition-transform`}>
                  {f.icon}
                </div>
                <h4 className="text-xl font-bold text-slate-900 mb-4">{f.title}</h4>
                <p className="text-slate-600 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING SECTION */}
      <section id="planos" className="py-24 bg-white relative overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-20 reveal">
            <h3 className="text-4xl md:text-5xl font-extrabold text-slate-900 mb-6">Planos Transparentes</h3>
            <p className="text-lg text-slate-600">Escala sem surpresas. Escolha o plano ideal para sua equipe.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {/* STARTER */}
            <div className="bg-white rounded-3xl p-8 border border-slate-200 hover:shadow-xl transition-all reveal">
              <h4 className="text-xl font-bold text-slate-900 mb-2">Starter</h4>
              <p className="text-slate-500 text-sm mb-6">Ideal para pequenas equipes de vendas.</p>
              <div className="mb-8">
                <span className="text-4xl font-extrabold text-slate-900">R$ 197</span>
                <span className="text-slate-500">/mês</span>
              </div>
              <ul className="space-y-4 mb-10">
                {['Até 5 operadores', 'Discador Básico', 'CRM Integrado', 'Suporte via Ticket'].map((item, i) => (
                  <li key={i} className="flex items-center text-slate-600 text-sm">
                    <CheckCircle2 size={16} className="text-brand-500 mr-3" /> {item}
                  </li>
                ))}
              </ul>
              <Link to="/login" className="block w-full py-4 bg-slate-100 hover:bg-slate-200 text-slate-900 font-bold rounded-2xl text-center transition-colors">Escolher Starter</Link>
            </div>

            {/* PROFESSIONAL - MOST POPULAR */}
            <div className="bg-slate-900 rounded-3xl p-8 border-2 border-brand-500 shadow-2xl shadow-brand-500/20 relative reveal transform scale-105 z-10">
              <div className="absolute top-0 right-8 -translate-y-1/2 bg-brand-500 text-white text-[10px] font-bold uppercase tracking-widest px-4 py-1.5 rounded-full">Destaque</div>
              <h4 className="text-xl font-bold text-white mb-2">Professional</h4>
              <p className="text-white/50 text-sm mb-6">O motor de tração para call centers em escala.</p>
              <div className="mb-8 text-white">
                <span className="text-4xl font-extrabold">R$ 497</span>
                <span className="text-white/50">/mês</span>
              </div>
              <ul className="space-y-4 mb-10 text-white/80">
                {['Operadores ilimitados', 'Discador Preditivo IA', 'Analytics Avançado', 'Gestão de DNC', 'Suporte Prioritário 24/7'].map((item, i) => (
                  <li key={i} className="flex items-center text-sm">
                    <CheckCircle2 size={16} className="text-brand-400 mr-3" /> {item}
                  </li>
                ))}
              </ul>
              <Link to="/login" className="block w-full py-4 bg-brand-500 hover:bg-brand-600 text-white font-bold rounded-2xl text-center transition-all shadow-lg shadow-brand-500/30">Assinar Professional</Link>
            </div>

            {/* ENTERPRISE */}
            <div className="bg-white rounded-3xl p-8 border border-slate-200 hover:shadow-xl transition-all reveal">
              <h4 className="text-xl font-bold text-slate-900 mb-2">Enterprise</h4>
              <p className="text-slate-500 text-sm mb-6">Segurança e escala para grandes operações.</p>
              <div className="mb-8">
                <span className="text-4xl font-extrabold text-slate-900">Sob Consulta</span>
              </div>
              <ul className="space-y-4 mb-10">
                {['Multi-Empresa', 'API de Integração', 'Account Manager Dedicado', 'SLA Garantido'].map((item, i) => (
                  <li key={i} className="flex items-center text-slate-600 text-sm">
                    <CheckCircle2 size={16} className="text-brand-500 mr-3" /> {item}
                  </li>
                ))}
              </ul>
              <Link to="/login" className="block w-full py-4 border border-slate-300 hover:bg-slate-50 text-slate-700 font-bold rounded-2xl text-center transition-colors">Falar com Consultor</Link>
            </div>
          </div>
        </div>
      </section>

      {/* CTA SECTION */}
      <section className="py-24 bg-brand-600 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-full opacity-10">
          <div className="absolute top-10 left-10 w-96 h-96 bg-white rounded-full blur-3xl"></div>
          <div className="absolute bottom-10 right-10 w-96 h-96 bg-blue-300 rounded-full blur-3xl"></div>
        </div>
        <div className="max-w-5xl mx-auto px-4 text-center relative z-10 reveal">
          <h2 className="text-4xl md:text-6xl font-extrabold text-white mb-8">Pronto para triplicar suas vendas?</h2>
          <p className="text-xl text-white/80 mb-12 max-w-2xl mx-auto">Junte-se a centenas de empresas que automatizaram suas operações e alcançaram novos patamares de receita.</p>
          <Link to="/login" className="inline-flex items-center bg-white text-brand-600 px-10 py-5 rounded-full font-bold text-xl shadow-2xl hover:scale-105 active:scale-95 transition-all">
            Começar Agora Mesmo — É Grátis
            <ArrowRight className="ml-3" />
          </Link>
          <p className="text-white/50 text-sm mt-6 font-medium">Não é necessário cartão de crédito • Configuração em 5 minutos</p>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="bg-slate-950 text-white pt-20 pb-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-4 gap-12 mb-16">
            <div className="col-span-2">
              <div className="flex items-center space-x-2 mb-6">
                <PhoneCall className="h-7 w-7 text-brand-500" />
                <span className="text-2xl font-bold">VoxFlow</span>
              </div>
              <p className="text-slate-400 max-w-sm leading-relaxed">
                A plataforma definitiva para call centers que buscam escala, produtividade e resultados reais através de tecnologia inteligente.
              </p>
            </div>
            <div>
              <h5 className="font-bold mb-6 text-sm uppercase tracking-widest text-brand-500">Links Rápidos</h5>
              <ul className="space-y-4 text-slate-400 text-sm">
                <li><a href="#funcionalidades" className="hover:text-white transition-colors">Funcionalidades</a></li>
                <li><a href="#como-funciona" className="hover:text-white transition-colors">Como Funciona</a></li>
                <li><a href="#planos" className="hover:text-white transition-colors">Preços</a></li>
                <li><Link to="/login" className="hover:text-white transition-colors">Login</Link></li>
              </ul>
            </div>
            <div>
              <h5 className="font-bold mb-6 text-sm uppercase tracking-widest text-brand-500">Suporte</h5>
              <ul className="space-y-4 text-slate-400 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">Central de Ajuda</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Status do Sistema</a></li>
                <li><a href="#" className="hover:text-white transition-colors">API Docs</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Fale Conosco</a></li>
              </ul>
            </div>
          </div>
          
          <div className="pt-10 border-t border-white/5 flex flex-col md:flex-row justify-between items-center text-slate-500 text-xs">
            <div className="flex items-center space-x-6 mb-4 md:mb-0">
              <span>© 2025 VoxFlow Inc.</span>
              <a href="#" className="hover:text-white transition-colors">Privacidade</a>
              <a href="#" className="hover:text-white transition-colors">Termos</a>
            </div>
            <div className="flex items-center">
              Desenvolvido com <Heart size={12} className="text-red-500 mx-1 fill-current" /> para líderes de vendas.
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
