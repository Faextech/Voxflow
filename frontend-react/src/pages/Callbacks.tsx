import { useState } from 'react'
import { useGet, useMut } from '@/hooks/useApi'
import { Card } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { statusBadge } from '@/components/ui/Badge'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import toast from 'react-hot-toast'
import type { CallbackItem } from '@/types'

const PER = 50

export default function Callbacks() {
  const [tab,  setTab]  = useState<'pending' | 'done'>('pending')
  const [page, setPage] = useState(1)

  const { data, isLoading, refetch } = useGet<{ callbacks: CallbackItem[]; total: number; page: number; per_page: number }>(
    ['callbacks', tab, String(page)],
    `/api/callbacks?status=${tab}&per_page=${PER}&page=${page}`
  )

  const remove = useMut('delete', (v: { id: number }) => `/api/callbacks/${v.id}`)

  async function del(id: number) {
    try { await remove.mutateAsync({ id }); toast.success('Removido'); refetch() }
    catch { toast.error('Erro') }
  }

  const callbacks = data?.callbacks ?? []
  const total     = data?.total ?? 0
  const pages     = Math.max(1, Math.ceil(total / PER))

  function fmtScheduled(cb: CallbackItem) {
    const dt = cb.scheduled_for ?? cb.scheduled_at
    if (!dt) return '—'
    return new Date(dt).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-lg font-semibold text-slate-100">Retornos</h1>

      <div className="flex gap-1 bg-slate-800 border border-slate-700 rounded-lg p-1 w-fit">
        {(['pending', 'done'] as const).map(t => (
          <button key={t} onClick={() => { setTab(t); setPage(1) }}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === t ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}>
            {t === 'pending' ? 'Pendentes' : 'Concluídos'}
          </button>
        ))}
      </div>

      <Card>
        <Table
          columns={[
            { key: 'lead_name',  header: 'Lead',       render: r => <span className="font-medium text-slate-200">{r.lead_name ?? `#${r.lead_id}`}</span> },
            { key: 'phone',      header: 'Telefone'    },
            { key: 'notes',      header: 'Observação', render: r => <span className="text-slate-400 truncate max-w-xs block">{r.notes ?? '—'}</span> },
            { key: 'scheduled',  header: 'Agendado',   render: r => <span className="text-slate-400">{fmtScheduled(r)}</span> },
            { key: 'priority',   header: 'Prioridade', render: r => {
              const colors: Record<string, string> = { high: 'text-red-400', medium: 'text-amber-400', low: 'text-slate-400' }
              return <span className={`text-xs font-medium ${colors[r.priority] ?? 'text-slate-400'}`}>{r.priority}</span>
            }},
            { key: 'status',     header: 'Status',     render: r => statusBadge(r.status) },
            { key: 'del', header: '', width: '50px',   render: r => (
              <button onClick={() => del(r.id)} className="text-slate-500 hover:text-red-400 p-1 transition-colors text-xs">✕</button>
            )},
          ]}
          data={callbacks}
          keyFn={r => r.id}
          loading={isLoading}
          empty="Nenhum retorno encontrado."
        />
        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700">
            <span className="text-xs text-slate-400">Página {page} de {pages} • {total} resultados</span>
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" disabled={page <= 1}    onClick={() => setPage(p => p - 1)}><ChevronLeft size={14} /> Anterior</Button>
              <Button size="sm" variant="ghost" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>Próxima <ChevronRight size={14} /></Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
