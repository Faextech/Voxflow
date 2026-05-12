import { useState } from 'react'
import { useGet, useMut } from '@/hooks/useApi'
import { Card } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { statusBadge } from '@/components/ui/Badge'
import { Plus, Search, ChevronLeft, ChevronRight, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import type { Lead, Campaign } from '@/types'

export default function Leads() {
  const [page,     setPage]     = useState(1)
  const [search,   setSearch]   = useState('')
  const [campaign, setCampaign] = useState('')
  const [status,   setStatus]   = useState('')
  const [showNew,  setShowNew]  = useState(false)
  const [form,     setForm]     = useState<Record<string, string>>({})

  const { data, isLoading, refetch } = useGet<{ leads: Lead[]; total: number; pages: number }>(
    ['leads', String(page), search, campaign, status],
    `/api/leads?page=${page}&per_page=50&search=${encodeURIComponent(search)}&campaign_id=${campaign}&status=${status}`,
    undefined,
    { keepPreviousData: true } as object
  )

  const { data: campsData } = useGet<{ campaigns: Campaign[] }>(['campaigns'], '/api/campaigns')
  const campaigns = campsData?.campaigns ?? []

  const create = useMut('post',   '/api/lead',                              [['leads']])
  const remove = useMut('delete', (v: { id: number }) => `/api/lead/${v.id}`, [['leads']])

  async function handleCreate() {
    if (!form.name || !form.numero_1) return toast.error('Nome e telefone são obrigatórios')
    try {
      await create.mutateAsync(form)
      toast.success('Lead criado')
      setShowNew(false); setForm({}); refetch()
    } catch (e: unknown) { toast.error((e as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Erro') }
  }

  async function handleDelete(id: number) {
    if (!confirm('Remover este lead?')) return
    try { await remove.mutateAsync({ id }); toast.success('Removido'); refetch() }
    catch { toast.error('Erro ao remover') }
  }

  const leads = data?.leads ?? []
  const total = data?.total ?? 0
  const pages = data?.pages ?? 1
  const set   = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }))

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Leads</h1>
          <p className="text-sm text-slate-400">{total} leads cadastrados</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => window.location.href = '/react/app/import'}>Importar CSV</Button>
          <Button onClick={() => setShowNew(true)}><Plus size={15} /> Novo lead</Button>
        </div>
      </div>

      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input className="pl-9" placeholder="Buscar por nome ou telefone..."
            value={search} onChange={e => { setSearch(e.target.value); setPage(1) }} />
        </div>
        <select className="w-48" value={campaign} onChange={e => { setCampaign(e.target.value); setPage(1) }}>
          <option value="">Todas campanhas</option>
          {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select className="w-40" value={status} onChange={e => { setStatus(e.target.value); setPage(1) }}>
          <option value="">Todos status</option>
          <option value="new">Novo</option>
          <option value="called">Chamado</option>
          <option value="answered">Atendido</option>
          <option value="no_answer">Não atendeu</option>
          <option value="converted">Convertido</option>
        </select>
      </div>

      <Card>
        <Table
          columns={[
            { key: 'name',         header: 'Nome',     render: r => <span className="font-medium text-slate-200">{r.name}</span> },
            { key: 'numero_1',     header: 'Telefone', render: r => r.numero_1 },
            { key: 'email',        header: 'Email',    render: r => <span className="text-slate-400">{r.email ?? '—'}</span> },
            { key: 'company_name', header: 'Empresa',  render: r => <span className="text-slate-400">{r.company_name ?? '—'}</span> },
            { key: 'status',       header: 'Status',   render: r => statusBadge(r.status) },
            { key: 'campaign_id',  header: 'Campanha', render: r => {
              const c = campaigns.find(c => c.id === r.campaign_id)
              return <span className="text-slate-400">{c?.name ?? `#${r.campaign_id}`}</span>
            }},
            { key: 'actions', header: '', width: '50px', render: r => (
              <button onClick={() => handleDelete(r.id)} className="text-slate-500 hover:text-red-400 transition-colors p-1">
                <Trash2 size={14} />
              </button>
            )},
          ]}
          data={leads}
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

      <Modal open={showNew} onClose={() => setShowNew(false)} title="Novo Lead">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-xs text-slate-400 mb-1.5">Nome *</label>
              <input value={form.name ?? ''} onChange={e => set('name', e.target.value)} placeholder="Nome completo" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Telefone 1 *</label>
              <input value={form.numero_1 ?? ''} onChange={e => set('numero_1', e.target.value)} placeholder="+5511999990000" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Telefone 2</label>
              <input value={form.numero_2 ?? ''} onChange={e => set('numero_2', e.target.value)} />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Email</label>
              <input type="email" value={form.email ?? ''} onChange={e => set('email', e.target.value)} />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Empresa</label>
              <input value={form.company_name ?? ''} onChange={e => set('company_name', e.target.value)} />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-slate-400 mb-1.5">Campanha</label>
              <select value={form.campaign_id ?? ''} onChange={e => set('campaign_id', e.target.value)}>
                <option value="">Selecione...</option>
                {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowNew(false)}>Cancelar</Button>
            <Button onClick={handleCreate} loading={create.isPending}>Criar</Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
