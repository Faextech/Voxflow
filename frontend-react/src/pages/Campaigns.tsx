import { useState } from 'react'
import { useGet, useMut } from '@/hooks/useApi'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge, statusBadge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Play, Pause, Square, Plus, Settings } from 'lucide-react'
import toast from 'react-hot-toast'
import type { Campaign } from '@/types'

function CampaignForm({ initial, onSave, onClose }: {
  initial?: Partial<Campaign>; onSave: (d: Partial<Campaign>) => void; onClose: () => void
}) {
  const [form, setForm] = useState<Partial<Campaign>>(initial ?? {
    name: '', dial_mode: 'sequential', caller_id_pool: '',
    ring_timeout_seconds: 50, allowed_hours_start: 8, allowed_hours_end: 20,
    allowed_timezone: 'America/Sao_Paulo', allowed_weekdays: '1,2,3,4,5',
  })
  const set = (k: keyof Campaign, v: any) => setForm(p => ({ ...p, [k]: v }))

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <label className="block text-xs text-slate-400 mb-1.5">Nome da campanha *</label>
          <input value={form.name ?? ''} onChange={e => set('name', e.target.value)} placeholder="Ex: Leads B2B Maio" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1.5">Modo de discagem</label>
          <select value={form.dial_mode ?? 'sequential'} onChange={e => set('dial_mode', e.target.value)}>
            <option value="sequential">Sequencial</option>
            <option value="predictive">Preditivo</option>
            <option value="power">Power</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1.5">Timeout por ligação (s)</label>
          <input type="number" value={form.ring_timeout_seconds ?? 50} onChange={e => set('ring_timeout_seconds', +e.target.value)} />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1.5">Horário início</label>
          <input type="number" min={0} max={23} value={form.allowed_hours_start ?? 8} onChange={e => set('allowed_hours_start', +e.target.value)} />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1.5">Horário fim</label>
          <input type="number" min={0} max={23} value={form.allowed_hours_end ?? 20} onChange={e => set('allowed_hours_end', +e.target.value)} />
        </div>
        <div className="col-span-2">
          <label className="block text-xs text-slate-400 mb-1.5">Pool de Caller IDs (um por linha)</label>
          <textarea
            rows={3}
            value={(form.caller_id_pool ?? '').replace(/,/g, '\n')}
            onChange={e => set('caller_id_pool', e.target.value.replace(/\n/g, ','))}
            placeholder="+5511999990000&#10;+5511888880000"
          />
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onClick={onClose}>Cancelar</Button>
        <Button onClick={() => onSave(form)}>Salvar</Button>
      </div>
    </div>
  )
}

export default function Campaigns() {
  const [showNew,   setShowNew]   = useState(false)
  const [editItem,  setEditItem]  = useState<Campaign | null>(null)

  const { data, isLoading, refetch } = useGet<{ campaigns: Campaign[] }>(['campaigns'], '/api/campaigns')
  const campaigns = data?.campaigns ?? []

  const create  = useMut('post',  '/api/campaign',                    [['campaigns']])
  const update  = useMut('patch', (v: any) => `/api/campaign/${v.id}`, [['campaigns']])
  const start   = useMut('post',  (v: any) => `/api/dialer/auto/start`, [['campaigns']])
  const pause   = useMut('post',  '/api/dialer/auto/pause',            [['campaigns']])
  const stop    = useMut('post',  '/api/dialer/auto/stop',             [['campaigns']])

  async function handleSave(form: Partial<Campaign>) {
    try {
      if (editItem) {
        await update.mutateAsync({ ...form, id: editItem.id })
        toast.success('Campanha atualizada')
      } else {
        await create.mutateAsync(form)
        toast.success('Campanha criada')
      }
      setShowNew(false); setEditItem(null)
    } catch (e: any) {
      toast.error(e?.response?.data?.error ?? 'Erro ao salvar')
    }
  }

  async function handleStart(id: number) {
    try {
      await start.mutateAsync({ campaign_id: id })
      toast.success('Discador iniciado'); refetch()
    } catch (e: any) { toast.error(e?.response?.data?.error ?? 'Erro') }
  }

  async function handlePause() {
    try { await pause.mutateAsync({}); toast.success('Pausado'); refetch() }
    catch (e: any) { toast.error(e?.response?.data?.error ?? 'Erro') }
  }

  async function handleStop() {
    try { await stop.mutateAsync({}); toast.success('Parado'); refetch() }
    catch (e: any) { toast.error(e?.response?.data?.error ?? 'Erro') }
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Campanhas</h1>
          <p className="text-sm text-slate-400">{campaigns.length} campanhas cadastradas</p>
        </div>
        <Button onClick={() => setShowNew(true)}><Plus size={15} /> Nova campanha</Button>
      </div>

      <Card>
        <CardBody className="p-0">
          {isLoading && <div className="text-center py-8 text-slate-500">Carregando...</div>}
          {!isLoading && campaigns.length === 0 && (
            <div className="text-center py-8 text-slate-500">
              Nenhuma campanha encontrada.
            </div>
          )}
          <div className="divide-y divide-slate-700/50">
            {campaigns.map(c => {
              const progress = c.leads_total > 0 ? Math.round((c.leads_called / c.leads_total) * 100) : 0
              const running  = c.status === 'running'
              const paused   = c.status === 'paused'
              return (
                <div key={c.id} className="px-6 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-medium text-slate-200">{c.name}</span>
                        {statusBadge(c.status)}
                        <Badge label={c.dial_mode} color="indigo" />
                      </div>
                      <div className="text-xs text-slate-500 space-x-3">
                        <span>Total: {c.leads_total}</span>
                        <span>Chamados: {c.leads_called}</span>
                        <span>Atendidos: {c.leads_answered}</span>
                      </div>
                      <div className="mt-2 flex items-center gap-2">
                        <div className="flex-1 max-w-48 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                          <div className="h-full bg-indigo-500 rounded-full" style={{ width: progress + '%' }} />
                        </div>
                        <span className="text-xs text-slate-400">{progress}%</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <button onClick={() => setEditItem(c)} className="p-1.5 text-slate-400 hover:text-slate-200 transition-colors" title="Configurar">
                        <Settings size={15} />
                      </button>
                      {!running && !paused && (
                        <Button size="sm" variant="secondary" onClick={() => handleStart(c.id)}>
                          <Play size={13} /> Iniciar
                        </Button>
                      )}
                      {running && (
                        <Button size="sm" variant="secondary" onClick={handlePause}>
                          <Pause size={13} /> Pausar
                        </Button>
                      )}
                      {(running || paused) && (
                        <Button size="sm" variant="danger" onClick={handleStop}>
                          <Square size={13} /> Parar
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </CardBody>
      </Card>

      <Modal open={showNew} onClose={() => setShowNew(false)} title="Nova Campanha" size="lg">
        <CampaignForm onSave={handleSave} onClose={() => setShowNew(false)} />
      </Modal>
      {editItem && (
        <Modal open={true} onClose={() => setEditItem(null)} title={`Editar: ${editItem.name}`} size="lg">
          <CampaignForm initial={editItem} onSave={handleSave} onClose={() => setEditItem(null)} />
        </Modal>
      )}
    </div>
  )
}
