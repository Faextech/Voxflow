import { useState } from 'react'
import { useGet } from '@/hooks/useApi'
import { Card } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { statusBadge } from '@/components/ui/Badge'
import { Download, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '@/api/client'
import toast from 'react-hot-toast'
import type { Call } from '@/types'

function fmtDuration(call: Call) {
  const sec = call.duration_seconds ?? call.duration ?? 0
  if (!sec) return '—'
  const m = Math.floor(sec / 60), s = sec % 60
  return `${m}m ${String(s).padStart(2, '0')}s`
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

export default function Calls() {
  const [page, setPage] = useState(1)
  const [from, setFrom] = useState('')
  const [to,   setTo]   = useState('')

  // API returns flat array; we slice client-side for pagination
  const PER = 50
  const { data: raw, isLoading } = useGet<Call[] | { calls: Call[]; total: number; pages: number }>(
    ['calls', from, to],
    `/api/calls?from=${from}&to=${to}`,
    undefined,
    { keepPreviousData: true } as object
  )

  const allCalls: Call[] = Array.isArray(raw) ? raw : ((raw as Record<string, unknown>)?.calls as Call[] ?? [])
  const total  = allCalls.length
  const pages  = Math.max(1, Math.ceil(total / PER))
  const calls  = allCalls.slice((page - 1) * PER, page * PER)

  async function exportCSV() {
    try {
      const res = await api.get('/api/analytics/export/calls', {
        params: { from, to }, responseType: 'blob',
      })
      const url = URL.createObjectURL(res.data)
      const a   = document.createElement('a')
      a.href = url; a.download = 'chamadas.csv'; a.click()
      URL.revokeObjectURL(url)
    } catch { toast.error('Erro ao exportar') }
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Chamadas</h1>
          <p className="text-sm text-slate-400">{total} chamadas registradas</p>
        </div>
        <Button variant="secondary" onClick={exportCSV}><Download size={14} /> Exportar CSV</Button>
      </div>

      <div className="flex gap-3">
        <div>
          <label className="block text-xs text-slate-400 mb-1">De</label>
          <input type="date" value={from} onChange={e => { setFrom(e.target.value); setPage(1) }} className="w-auto" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Até</label>
          <input type="date" value={to} onChange={e => { setTo(e.target.value); setPage(1) }} className="w-auto" />
        </div>
      </div>

      <Card>
        <Table
          columns={[
            { key: 'lead_name',   header: 'Lead',       render: r => <span className="font-medium text-slate-200">{r.lead_name ?? '—'}</span> },
            { key: 'phone_dialed',header: 'Telefone',   render: r => r.phone_dialed ?? r.phone_number ?? '—' },
            { key: 'campaign_name',header:'Campanha',   render: r => <span className="text-slate-400">{r.campaign_name ?? '—'}</span> },
            { key: 'status',      header: 'Status',     render: r => statusBadge(r.status) },
            { key: 'disposition', header: 'Disposição', render: r => r.disposition ? statusBadge(r.disposition) : <span className="text-slate-500">—</span> },
            { key: 'duration',    header: 'Duração',    render: r => fmtDuration(r) },
            { key: 'created_at',  header: 'Data/Hora',  render: r => <span className="text-slate-400">{fmtDate(r.created_at)}</span> },
          ]}
          data={calls}
          keyFn={r => r.id}
          loading={isLoading}
        />
        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700">
            <span className="text-xs text-slate-400">Página {page} de {pages} • {total} resultados</span>
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" disabled={page <= 1}    onClick={() => setPage(p => p - 1)}><ChevronLeft  size={14} /> Anterior</Button>
              <Button size="sm" variant="ghost" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>Próxima <ChevronRight size={14} /></Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
