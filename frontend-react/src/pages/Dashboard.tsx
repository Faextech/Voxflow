import { useGet } from '@/hooks/useApi'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { statusBadge, Badge } from '@/components/ui/Badge'
import type { DashboardMetrics, Campaign } from '@/types'
import { useNavigate } from 'react-router-dom'

function MetricCard({ label, value, sub, accent }: {
  label: string; value: string | number; sub?: string; accent?: string
}) {
  return (
    <div className="metric-card" style={accent ? { borderTop: `3px solid ${accent}` } : {}}>
      <small>{label}</small>
      <h3 style={accent ? { color: accent } : {}}>{value}</h3>
      {sub && <span className="metric-sub">{sub}</span>}
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()

  const { data: metrics, isLoading: lm } = useGet<DashboardMetrics>(
    ['dashboard-metrics'], '/api/dashboard/metrics', undefined, { refetchInterval: 30_000 }
  )
  const { data: campsData } = useGet<{ campaigns: Campaign[] }>(
    ['campaigns'], '/api/campaigns', undefined, { refetchInterval: 30_000 }
  )

  const campaigns = campsData?.campaigns ?? []
  const m = metrics

  const answerRate = m && m.total_calls > 0
    ? ((m.answered_calls / m.total_calls) * 100).toFixed(1) + '%'
    : '0%'

  const avgDur = m
    ? Math.floor((m.avg_duration ?? 0) / 60) + 'm ' + ((m.avg_duration ?? 0) % 60) + 's'
    : '—'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Painel de operação em tempo real</p>
        </div>
      </div>

      {/* KPI cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px,1fr))', gap: '16px' }}>
        <MetricCard label="Chamadas hoje"    value={lm ? '…' : (m?.calls_today ?? 0)}   accent="var(--accent)" />
        <MetricCard label="Taxa atendimento" value={lm ? '…' : answerRate}               accent="var(--accent-green)" />
        <MetricCard label="Chamadas total"   value={lm ? '…' : (m?.total_calls ?? 0)}   />
        <MetricCard label="Total leads"      value={lm ? '…' : (m?.total_leads ?? 0)}   />
        <MetricCard label="Tempo médio"      value={lm ? '…' : avgDur}                  />
        <MetricCard
          label="Saldo"
          value={lm ? '…' : `R$ ${Number(m?.credit_balance ?? 0).toFixed(2)}`}
          accent="var(--accent-green)"
          sub="crédito disponível"
        />
      </div>

      {/* Campaign monitor */}
      <Card>
        <CardHeader
          title="Monitor de Campanhas"
          subtitle={`${campaigns.filter(c => c.status === 'running').length} campanhas ativas`}
          action={
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/app/campaigns')}>
              Ver todas →
            </button>
          }
        />
        {campaigns.length === 0 ? (
          <CardBody>
            <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-secondary)' }}>
              Nenhuma campanha encontrada.{' '}
              <button className="btn btn-ghost btn-sm" onClick={() => navigate('/app/campaigns')}>
                Criar campanha →
              </button>
            </div>
          </CardBody>
        ) : (
          <div>
            {campaigns.map(c => {
              const pct = c.leads_total > 0 ? Math.round((c.leads_called / c.leads_total) * 100) : 0
              return (
                <div key={c.id} style={{
                  display: 'flex', alignItems: 'center', gap: '16px',
                  padding: '14px 20px', borderBottom: '1px solid var(--border)',
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{c.name}</span>
                      {statusBadge(c.status)}
                      <Badge label={c.dial_mode} color="blue" />
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', gap: '12px' }}>
                      <span>{c.leads_called}/{c.leads_total} leads</span>
                      <span>{c.leads_answered} atendidas</span>
                    </div>
                  </div>
                  <div style={{ width: '140px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      <span>Progresso</span><span>{pct}%</span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: pct + '%' }} />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}
