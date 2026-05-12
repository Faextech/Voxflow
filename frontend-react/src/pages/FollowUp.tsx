import { useState } from 'react'
import { useGet, useMut } from '@/hooks/useApi'
import { Card, CardBody } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Badge, statusBadge } from '@/components/ui/Badge'
import { Plus, Trash2, Pencil } from 'lucide-react'
import toast from 'react-hot-toast'
import type { FollowUpSequence, FollowUpTask, FollowUpStep } from '@/types'

const ACTION_LABELS: Record<string, string> = { email: 'E-mail', whatsapp: 'WhatsApp', ligar: 'Ligar' }

function StepRow({ step, onChange, onRemove }: {
  step: FollowUpStep; onChange: (s: FollowUpStep) => void; onRemove: () => void
}) {
  return (
    <div className="flex gap-2 items-center bg-slate-700/40 rounded-lg p-3">
      <select className="w-28" value={step.action} onChange={e => onChange({ ...step, action: e.target.value as FollowUpStep['action'] })}>
        <option value="email">E-mail</option>
        <option value="whatsapp">WhatsApp</option>
        <option value="ligar">Ligar</option>
      </select>
      <input type="number" className="w-24" placeholder="Minutos" value={step.delay_minutes}
        onChange={e => onChange({ ...step, delay_minutes: +e.target.value })} />
      <input className="flex-1" placeholder="Mensagem / template" value={step.template}
        onChange={e => onChange({ ...step, template: e.target.value })} />
      <button onClick={onRemove} className="text-slate-500 hover:text-red-400 transition-colors p-1">
        <Trash2 size={14} />
      </button>
    </div>
  )
}

function SequenceForm({ initial, onSave, onClose }: {
  initial?: Partial<FollowUpSequence>; onSave: (d: Partial<FollowUpSequence>) => void; onClose: () => void
}) {
  const [name,    setName]    = useState(initial?.name    ?? '')
  const [trigger, setTrigger] = useState(initial?.trigger ?? 'nao_atendeu')
  const [steps,   setSteps]   = useState<FollowUpStep[]>(initial?.steps ?? [])

  function addStep() { setSteps(p => [...p, { delay_minutes: 60, action: 'email', template: '' }]) }
  function updateStep(i: number, s: FollowUpStep) { setSteps(p => p.map((x, j) => j === i ? s : x)) }
  function removeStep(i: number) { setSteps(p => p.filter((_, j) => j !== i)) }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <label className="block text-xs text-slate-400 mb-1.5">Nome da sequência</label>
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Ex: Pós não-atendimento" />
        </div>
        <div className="col-span-2">
          <label className="block text-xs text-slate-400 mb-1.5">Gatilho</label>
          <select value={trigger} onChange={e => setTrigger(e.target.value)}>
            <option value="nao_atendeu">Não atendeu</option>
            <option value="caixa_postal">Caixa postal</option>
            <option value="convertido">Convertido</option>
          </select>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-medium text-slate-400">Etapas</label>
          <Button size="sm" variant="ghost" onClick={addStep}><Plus size={13} /> Adicionar etapa</Button>
        </div>
        {steps.length === 0 && (
          <p className="text-xs text-slate-500 text-center py-4">Nenhuma etapa. Clique em "Adicionar etapa".</p>
        )}
        {steps.map((s, i) => (
          <StepRow key={i} step={s} onChange={v => updateStep(i, v)} onRemove={() => removeStep(i)} />
        ))}
      </div>

      <div className="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onClick={onClose}>Cancelar</Button>
        <Button onClick={() => onSave({ name, trigger, steps })}>Salvar</Button>
      </div>
    </div>
  )
}

export default function FollowUp() {
  const [tab,      setTab]      = useState<'sequences' | 'tasks'>('sequences')
  const [showNew,  setShowNew]  = useState(false)
  const [editItem, setEditItem] = useState<FollowUpSequence | null>(null)

  const { data: seqData, isLoading: loadSeq, refetch: refetchSeq } =
    useGet<FollowUpSequence[]>(['followup-sequences'], '/api/followup/sequences')

  const { data: taskData, isLoading: loadTasks } =
    useGet<{ tasks: FollowUpTask[]; total: number }>(
      ['followup-tasks'], '/api/followup/tasks?status=pending&per_page=50',
      undefined, { enabled: tab === 'tasks' }
    )

  const create   = useMut('post',   '/api/followup/sequences',                              [['followup-sequences']])
  const update   = useMut('put',    (v: { id: number }) => `/api/followup/sequences/${v.id}`,          [['followup-sequences']])
  const remove   = useMut('delete', (v: { id: number }) => `/api/followup/sequences/${v.id}`, [['followup-sequences']])
  const markSent = useMut('post',   (v: { id: number }) => `/api/followup/tasks/${v.id}/mark-sent`, [['followup-tasks']])
  const skip     = useMut('post',   (v: { id: number }) => `/api/followup/tasks/${v.id}/skip`,      [['followup-tasks']])

  async function handleSave(form: Partial<FollowUpSequence>) {
    try {
      if (editItem) {
        await update.mutateAsync({ ...form, id: editItem.id })
        toast.success('Sequência atualizada')
      } else {
        await create.mutateAsync(form)
        toast.success('Sequência criada')
      }
      setShowNew(false); setEditItem(null); refetchSeq()
    } catch (e: unknown) { toast.error((e as { response?: { data?: { error?: string } } })?.response?.data?.error ?? 'Erro') }
  }

  const sequences = seqData ?? []
  const tasks     = taskData?.tasks ?? []

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-100">Follow-up</h1>
        {tab === 'sequences' && (
          <Button onClick={() => setShowNew(true)}><Plus size={15} /> Nova sequência</Button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-800 border border-slate-700 rounded-lg p-1 w-fit">
        {(['sequences', 'tasks'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === t ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}>
            {t === 'sequences' ? 'Sequências' : 'Tarefas pendentes'}
          </button>
        ))}
      </div>

      {tab === 'sequences' && (
        <Card>
          <CardBody className="p-0">
            {loadSeq && <div className="text-center py-8 text-slate-500">Carregando...</div>}
            {!loadSeq && sequences.length === 0 && (
              <div className="text-center py-8 text-slate-500">Nenhuma sequência cadastrada.</div>
            )}
            <div className="divide-y divide-slate-700/50">
              {sequences.map(s => (
                <div key={s.id} className="px-6 py-4 flex items-center justify-between gap-4">
                  <div>
                    <p className="font-medium text-slate-200">{s.name}</p>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <Badge label={`Gatilho: ${s.trigger}`} color="indigo" />
                      <Badge label={`${s.steps?.length ?? 0} etapas`} color="slate" />
                      {s.steps?.map((step, i) => (
                        <Badge key={i} label={ACTION_LABELS[step.action] ?? step.action} color="blue" />
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button onClick={() => setEditItem(s)} className="text-slate-400 hover:text-slate-200 p-1 transition-colors">
                      <Pencil size={14} />
                    </button>
                    <button onClick={() => remove.mutateAsync({ id: s.id }).then(() => toast.success('Removida'))}
                      className="text-slate-400 hover:text-red-400 p-1 transition-colors">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {tab === 'tasks' && (
        <Card>
          <Table
            columns={[
              { key: 'lead_name', header: 'Lead',       render: r => <span className="font-medium text-slate-200">{r.lead_name ?? `#${r.lead_id}`}</span> },
              { key: 'action',    header: 'Ação',        render: r => <Badge label={ACTION_LABELS[r.action] ?? r.action} color="blue" /> },
              { key: 'template',  header: 'Mensagem',    render: r => <span className="text-slate-400 truncate max-w-xs block">{r.template || '—'}</span> },
              { key: 'scheduled_at', header: 'Agendado', render: r => <span className="text-slate-400">{new Date(r.scheduled_at).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}</span> },
              { key: 'status',    header: 'Status',      render: r => statusBadge(r.status) },
              { key: 'actions',   header: '', render: r => (
                <div className="flex gap-1">
                  <Button size="sm" variant="secondary" onClick={() => markSent.mutateAsync({ id: r.id })}>✓ Marcar</Button>
                  <Button size="sm" variant="ghost"    onClick={() => skip.mutateAsync({ id: r.id })}>Pular</Button>
                </div>
              )},
            ]}
            data={tasks}
            keyFn={r => r.id}
            loading={loadTasks}
            empty="Nenhuma tarefa pendente."
          />
        </Card>
      )}

      <Modal open={showNew} onClose={() => setShowNew(false)} title="Nova Sequência de Follow-up" size="lg">
        <SequenceForm onSave={handleSave} onClose={() => setShowNew(false)} />
      </Modal>
      {editItem && (
        <Modal open={true} onClose={() => setEditItem(null)} title={`Editar: ${editItem.name}`} size="lg">
          <SequenceForm initial={editItem} onSave={handleSave} onClose={() => setEditItem(null)} />
        </Modal>
      )}
    </div>
  )
}
