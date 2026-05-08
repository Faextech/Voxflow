import { useState } from 'react'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { useGet } from '@/hooks/useApi'
import { api } from '@/api/client'
import toast from 'react-hot-toast'
import { Download, TrendingUp, PhoneCall, Users, ListX } from 'lucide-react'
import type { DashboardMetrics } from '@/types'

export default function Reports() {
  const [from, setFrom] = useState('')
  const [to,   setTo]   = useState('')

  const { data: metrics } = useGet<DashboardMetrics>(['dashboard-metrics'], '/api/dashboard/metrics')

  async function exportCSV(type: 'leads' | 'calls' | 'dnc') {
    try {
      const params: Record<string, string> = {}
      if (type === 'calls') { if (from) params.from = from; if (to) params.to = to }
      const r = await api.get(`/api/analytics/export/${type}`, { params, responseType: 'blob' })
      const url = URL.createObjectURL(r.data)
      const a   = document.createElement('a')
      a.href = url; a.download = `${type}-${Date.now()}.csv`; a.click()
      URL.revokeObjectURL(url)
    } catch { toast.error('Erro ao exportar') }
  }

  const m = metrics

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Relatórios</h1>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { icon: PhoneCall,  label: 'Total chamadas',  value: m?.total_calls ?? '—',    color: 'text-indigo-400' },
          { icon: TrendingUp, label: 'Taxa atendimento', value: m ? ((m.answered_calls / (m.total_calls || 1)) * 100).toFixed(1) + '%' : '—', color: 'text-green-400' },
          { icon: Users,      label: 'Total leads',     value: m?.total_leads ?? '—',    color: 'text-blue-400'   },
          { icon: ListX,      label: 'Chamadas hoje',   value: m?.calls_today ?? '—',    color: 'text-amber-400'  },
        ].map(({ icon: Icon, label, value, color }) => (
          <div key={label} className="bg-slate-800 border border-slate-700 rounded-xl p-5">
            <Icon size={20} className={`${color} mb-2`} />
            <p className="text-2xl font-bold text-slate-100">{value}</p>
            <p className="text-xs text-slate-400 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Exports */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader title="Leads" subtitle="Export completo de leads" />
          <CardBody>
            <p className="text-xs text-slate-400 mb-4">Exporta todos os leads com status, telefone, campanha e histórico.</p>
            <Button variant="secondary" className="w-full justify-center" onClick={() => exportCSV('leads')}>
              <Download size={14} /> Baixar CSV
            </Button>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Chamadas" subtitle="Export com filtro por período" />
          <CardBody>
            <div className="flex gap-2 mb-4">
              <div className="flex-1">
                <label className="block text-xs text-slate-400 mb-1">De</label>
                <input type="date" value={from} onChange={e => setFrom(e.target.value)} />
              </div>
              <div className="flex-1">
                <label className="block text-xs text-slate-400 mb-1">Até</label>
                <input type="date" value={to} onChange={e => setTo(e.target.value)} />
              </div>
            </div>
            <Button variant="secondary" className="w-full justify-center" onClick={() => exportCSV('calls')}>
              <Download size={14} /> Baixar CSV
            </Button>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Lista DNC" subtitle="Todos os números bloqueados" />
          <CardBody>
            <p className="text-xs text-slate-400 mb-4">Exporta a lista completa de números na DNC com motivo e data.</p>
            <Button variant="secondary" className="w-full justify-center" onClick={() => exportCSV('dnc')}>
              <Download size={14} /> Baixar CSV
            </Button>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
