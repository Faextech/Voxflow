import { useGet } from '@/hooks/useApi'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'

interface AmdRow { campaign_id: number; campaign_name: string; total: number; voicemail: number; human: number; recovered: number }
interface Pipeline { id: number; name: string; stages?: Array<{ id: number; name: string; deal_count?: number }> }
interface Alert { level: string; message: string }

export default function Analytics() {
  const { data: pipelines } = useGet<{ pipelines: Pipeline[] }>(['analytics-pipelines'], '/api/analytics/pipelines')
  const { data: amd }       = useGet<Record<string, unknown>>(['analytics-amd'], '/api/analytics/dashboard')
  const { data: alerts }    = useGet<{ alerts: Alert[] }>(['analytics-alerts'], '/api/analytics/alerts')

  const alertList = alerts?.alerts ?? []
  const pipeList  = pipelines?.pipelines ?? []

  function alertStyle(level: string): React.CSSProperties {
    if (level === 'critical') return { background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.2)', color: 'var(--accent-red)' }
    if (level === 'warning')  return { background: 'rgba(217,119,6,0.1)',  border: '1px solid rgba(217,119,6,0.2)',  color: 'var(--accent-yellow)' }
    return { background: 'rgba(37,99,235,0.1)', border: '1px solid rgba(37,99,235,0.2)', color: 'var(--accent)' }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="page-header">
        <div>
          <h1>Analytics</h1>
          <p>Métricas e análise de desempenho</p>
        </div>
      </div>

      {alertList.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {alertList.map((a, i) => (
            <div key={i} className="alert" style={alertStyle(a.level)}>
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
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px,1fr))', gap: '16px', marginBottom: '24px' }}>
              {[
                { label: 'Total analisados', value: (amd.total_amd ?? 0) as number },
                { label: 'Caixas postais',   value: amd.voicemail_pct != null ? `${amd.voicemail_pct}%` : '—' },
                { label: 'Recuperados',      value: (amd.recovered ?? 0) as number },
                { label: 'Humanos',          value: amd.human_pct != null ? `${amd.human_pct}%` : '—' },
              ].map(({ label, value }) => (
                <div key={label} className="metric-card" style={{ textAlign: 'center' }}>
                  <h3 style={{ fontSize: '1.5rem' }}>{String(value)}</h3>
                  <small>{label}</small>
                </div>
              ))}
            </div>
            {Array.isArray(amd.by_campaign) && (amd.by_campaign as AmdRow[]).length > 0 && (
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      {['Campanha', 'Total', 'Caixa postal', 'Humano', 'Recuperados'].map(h => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(amd.by_campaign as AmdRow[]).map(row => (
                      <tr key={row.campaign_id}>
                        <td>{row.campaign_name}</td>
                        <td className="td-muted">{row.total}</td>
                        <td className="td-muted">{row.voicemail}</td>
                        <td className="td-muted">{row.human}</td>
                        <td className="td-muted">{row.recovered}</td>
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
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {pipeList.map(p => (
                <div key={p.id} className="panel" style={{ padding: '16px' }}>
                  <p style={{ fontWeight: 500, marginBottom: '8px' }}>{p.name}</p>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {p.stages?.map(s => (
                      <div key={s.id} className="metric-card" style={{ textAlign: 'center', padding: '8px 12px', minWidth: '80px' }}>
                        <h3 style={{ fontSize: '1.25rem' }}>{s.deal_count ?? 0}</h3>
                        <small style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '96px' }}>{s.name}</small>
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
