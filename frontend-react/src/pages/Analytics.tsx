import { useGet } from '@/hooks/useApi'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'

export default function Analytics() {
  const { data: pipelines } = useGet<any>(['analytics-pipelines'], '/api/analytics/pipelines')
  const { data: amd }       = useGet<any>(['analytics-amd'], '/api/analytics/dashboard')
  const { data: alerts }    = useGet<any>(['analytics-alerts'],   '/api/analytics/alerts')

  const alertList = alerts?.alerts ?? []
  const pipeList  = pipelines?.pipelines ?? []

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-lg font-semibold text-slate-100">Analytics</h1>

      {alertList.length > 0 && (
        <div className="space-y-2">
          {alertList.map((a: any, i: number) => (
            <div key={i} className={`flex items-center gap-3 px-4 py-3 rounded-lg border text-sm
              ${a.level === 'critical' ? 'bg-red-500/10 border-red-500/30 text-red-300'
              : a.level === 'warning'  ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
              : 'bg-blue-500/10 border-blue-500/30 text-blue-300'}`}>
              {a.level === 'critical' ? '🔴' : a.level === 'warning' ? '⚠️' : 'ℹ️'} {a.message}
            </div>
          ))}
        </div>
      )}

      {/* AMD metrics */}
      {amd && (
        <Card>
          <CardHeader title="AMD — Detecção de Caixa Postal" />
          <CardBody>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[
                { label: 'Total analisados', value: amd.total_amd     ?? 0 },
                { label: 'Caixas postais',   value: amd.voicemail_pct ?? '—', suffix: amd.voicemail_pct != null ? '%' : '' },
                { label: 'Recuperados',      value: amd.recovered     ?? 0 },
                { label: 'Humanos',          value: amd.human_pct     ?? '—', suffix: amd.human_pct != null ? '%' : '' },
              ].map(({ label, value, suffix = '' }) => (
                <div key={label} className="bg-slate-700/40 rounded-lg p-3 text-center">
                  <p className="text-xl font-bold text-slate-100">{value}{suffix}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{label}</p>
                </div>
              ))}
            </div>
            {amd.by_campaign?.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700">
                      {['Campanha', 'Total', 'Caixa postal', 'Humano', 'Recuperados'].map(h => (
                        <th key={h} className="text-left px-3 py-2 text-xs font-medium text-slate-400">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {amd.by_campaign.map((row: any) => (
                      <tr key={row.campaign_id} className="border-b border-slate-700/50">
                        <td className="px-3 py-2 text-slate-300">{row.campaign_name}</td>
                        <td className="px-3 py-2 text-slate-400">{row.total}</td>
                        <td className="px-3 py-2 text-slate-400">{row.voicemail}</td>
                        <td className="px-3 py-2 text-slate-400">{row.human}</td>
                        <td className="px-3 py-2 text-slate-400">{row.recovered}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* Pipelines */}
      {pipeList.length > 0 && (
        <Card>
          <CardHeader title="CRM — Pipelines" />
          <CardBody>
            <div className="space-y-3">
              {pipeList.map((p: any) => (
                <div key={p.id} className="border border-slate-700 rounded-lg p-4">
                  <p className="font-medium text-slate-200 mb-2">{p.name}</p>
                  <div className="flex gap-2 flex-wrap">
                    {p.stages?.map((s: any) => (
                      <div key={s.id} className="bg-slate-700/40 rounded px-3 py-2 text-center min-w-20">
                        <p className="text-sm font-bold text-slate-100">{s.deal_count ?? 0}</p>
                        <p className="text-xs text-slate-400 mt-0.5 truncate max-w-24">{s.name}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
