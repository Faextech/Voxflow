import { useState } from 'react'
import { useGet, useMut } from '@/hooks/useApi'
import { Card, CardBody } from '@/components/ui/Card'
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
  const set = (k: keyof Campaign, v: unknown) => setForm(p => ({ ...p, [k]: v }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div className="form-grid">
        <div className="full">
          <div className="field">
            <label>Nome da campanha *</label>
            <input value={form.name ?? ''} onChange={e => set('name', e.target.value)} placeholder="Ex: Leads B2B Maio" />
          </div>
        </div>
        <div className="field">
          <label>Modo de discagem</label>
          <select value={form.dial_mode ?? 'sequential'} onChange={e => set('dial_mode', e.target.value)}>
            <option value="sequential">Sequencial</option>
            <option value="predictive">Preditivo</option>
            <option value="power">Power</option>
          </select>
        </div>
        <div className="field">
          <label>Timeout por ligação (s)</label>
          <input type="number" value={form.ring_timeout_seconds ?? 50} onChange={e => set('ring_timeout_seconds', +e.target.value)} />
        </div>
        <div className="field">
          <label>Horário início</label>
          <input type="number" min={0} max={23} value={form.allowed_hours_start ?? 8} onChange={e => set('allowed_hours_start', +e.target.value)} />
        </div>
        <div className="field">
          <label>Horário fim</label>
          <input type="number" min={0} max={23} value={form.allowed_hours_end ?? 20} onChange={e => set('allowed_hours_end', +e.target.value)} />
        </div>
        <div className="full field">
          <label>Pool de Caller IDs (um por linha)</label>
          <textarea
            rows={3}
            value={(form.caller_id_pool ?? '').replace(/,/g, '\n')}
            onChange={e => set('caller_id_pool', e.target.value.replace(/\n/g, ','))}
            placeholder={'+5511999990000\n+5511888880000'}
          />
        </div>
      </div>
      <div className="actions-row">
        <Button variant="secondary" onClick={onClose}>Cancelar</Button>
        <Button onClick={() => onSave(form)}>Salvar</Button>
      </div>
    </div>
  )
}

export default function Campaigns() {
  const [showNew,  setShowNew]  = useState(false)
  const [editItem, setEditItem] = useState<Campaign | null>(null)

  const { data, isLoading, refetch } = useGet<{ campaigns: Campaign[] }>(['campaigns'], '/api/campaigns')
  const campaigns = data?.campaigns ?? []

  const create  = useMut('post',  '/api/campaign',                      [['campaigns']])
  const update  = useMut('patch', (v: { id: number }) => `/api/campaign/${v.id}`,  [['campaigns']])
  const start   = useMut('post',  '/api/dialer/auto/start',             [['campaigns']])
  const pause   = useMut('post',  '/api/dialer/auto/pause',             [['campaigns']])
  const stop    = useMut('post',  '/api/dialer/auto/stop',              [['campaigns']])

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
    } catch (e: unknown) {
      toast.error((e as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Erro ao salvar')
    }
  }

  async function handleStart(id: number) {
    try { await start.mutateAsync({ campaign_id: id }); toast.success('Discador iniciado'); refetch() }
    catch (e: unknown) { toast.error((e as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Erro') }
  }

  async function handlePause() {
    try { await pause.mutateAsync({}); toast.success('Pausado'); refetch() }
    catch (e: unknown) { toast.error((e as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Erro') }
  }

  async function handleStop() {
    try { await stop.mutateAsync({}); toast.success('Parado'); refetch() }
    catch (e: unknown) { toast.error((e as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Erro') }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="page-header">
        <div>
          <h1>Campanhas</h1>
          <p>{campaigns.length} campanhas cadastradas</p>
        </div>
        <Button onClick={() => setShowNew(true)}><Plus size={15} /> Nova campanha</Button>
      </div>

      <Card>
        <CardBody style={{ padding: 0 }}>
          {isLoading && (
            <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-secondary)' }}>
              Carregando...
            </div>
          )}
          {!isLoading && campaigns.length === 0 && (
            <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-secondary)' }}>
              Nenhuma campanha encontrada.
            </div>
          )}
          <div>
            {campaigns.map(c => {
              const progress = c.leads_total > 0 ? Math.round((c.leads_called / c.leads_total) * 100) : 0
              const running  = c.status === 'running'
              const paused   = c.status === 'paused'
              return (
                <div key={c.id} style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
                        <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{c.name}</span>
                        {statusBadge(c.status)}
                        <Badge label={c.dial_mode} color="indigo" />
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', gap: '12px' }}>
                        <span>Total: {c.leads_total}</span>
                        <span>Chamados: {c.leads_called}</span>
                        <span>Atendidos: {c.leads_answered}</span>
                      </div>
                      <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div className="progress-bar" style={{ flex: 1, maxWidth: '200px' }}>
                          <div className="progress-fill" style={{ width: progress + '%', background: 'var(--accent)' }} />
                        </div>
                        <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{progress}%</span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                      <button
                        onClick={() => setEditItem(c)}
                        className="btn btn-ghost btn-sm"
                        title="Configurar"
                        style={{ padding: '6px' }}
                      >
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
