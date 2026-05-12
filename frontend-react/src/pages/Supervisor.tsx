import { useGet, useMut } from '@/hooks/useApi'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { statusBadge } from '@/components/ui/Badge'
import { Mic, Volume2, Radio } from 'lucide-react'
import toast from 'react-hot-toast'
import type { Agent } from '@/types'

type ApiErr = { response?: { data?: { error?: string } } }

export default function Supervisor() {
  const { data, isLoading, refetch } = useGet<{ agents: Agent[]; total_active_conferences: number }>(
    ['supervisor'], '/api/supervisor/realtime', undefined, { refetchInterval: 10_000 }
  )

  const listenMut   = useMut('post', '/api/supervisor/listen-live')
  const whisperMut  = useMut('post', '/api/supervisor/whisper')

  async function listen(conference_name: string) {
    try {
      await listenMut.mutateAsync({ conference_name } as never)
      toast.success('Entrando como ouvinte...')
    } catch (e: unknown) { toast.error((e as ApiErr)?.response?.data?.error ?? 'Erro') }
  }

  async function whisper(conference_name: string, mode: 'whisper' | 'barge') {
    try {
      await whisperMut.mutateAsync({ conference_name, mode } as never)
      toast.success(mode === 'whisper' ? 'Modo whisper ativado' : 'Modo barge ativado')
    } catch (e: unknown) { toast.error((e as ApiErr)?.response?.data?.error ?? 'Erro') }
  }

  const agents = data?.agents ?? []
  const online = agents.filter(a => a.status !== 'offline').length
  const onCall = agents.filter(a => a.active_call).length

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Supervisor</h1>
          <p className="text-sm text-slate-400">{online} online · {onCall} em chamada</p>
        </div>
        <Button variant="secondary" onClick={() => refetch()}>Atualizar</Button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Agentes online', value: online },
          { label: 'Em chamada',     value: onCall },
          { label: 'Conferências',   value: data?.total_active_conferences ?? 0 },
        ].map(({ label, value }) => (
          <div key={label} className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
            <p className="text-2xl font-bold text-slate-100">{value}</p>
            <p className="text-xs text-slate-400 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      <Card>
        <CardHeader title="Agentes" />
        <CardBody className="p-0">
          {isLoading && <div className="text-center py-8 text-slate-500">Carregando...</div>}
          {!isLoading && agents.length === 0 && (
            <div className="text-center py-8 text-slate-500">Nenhum agente cadastrado.</div>
          )}
          <div className="divide-y divide-slate-700/50">
            {agents.map(a => (
              <div key={a.id} className="px-6 py-4 flex items-center gap-4">
                <div className="w-8 h-8 rounded-full bg-indigo-600/20 flex items-center justify-center text-indigo-400 text-sm font-bold shrink-0">
                  {a.name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-200">{a.name}</span>
                    {statusBadge(a.status)}
                  </div>
                  {a.active_call ? (
                    <p className="text-xs text-slate-400 mt-0.5">
                      Em chamada com {a.active_call.lead_name ?? a.active_call.phone_number}
                    </p>
                  ) : (
                    <p className="text-xs text-slate-500 mt-0.5">
                      {a.last_active ? `Último acesso: ${new Date(a.last_active).toLocaleTimeString('pt-BR')}` : 'Sem atividade recente'}
                    </p>
                  )}
                </div>
                {a.active_call && (
                  <div className="flex gap-2 shrink-0">
                    <Button size="sm" variant="secondary" title="Ouvir" onClick={() => listen(a.active_call!.conference_name)}>
                      <Volume2 size={13} /> Ouvir
                    </Button>
                    <Button size="sm" variant="secondary" title="Whisper" onClick={() => whisper(a.active_call!.conference_name, 'whisper')}>
                      <Mic size={13} /> Whisper
                    </Button>
                    <Button size="sm" variant="secondary" title="Barge" onClick={() => whisper(a.active_call!.conference_name, 'barge')}>
                      <Radio size={13} /> Barge
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
