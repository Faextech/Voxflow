import { useGet } from '@/hooks/useApi'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { DollarSign, TrendingDown, Clock } from 'lucide-react'

interface Balance {
  credit_balance:   number
  cost_per_minute:  number
  estimated_minutes: number
}

interface Transaction {
  id:          number
  amount:      number
  type:        string
  description: string
  created_at:  string
}

function fmtBRL(v: number) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)
}

export default function Credito() {
  const { data: balance } = useGet<Balance>(['billing-balance'], '/api/billing/balance', undefined, { refetchInterval: 60_000 })
  const { data: txRaw }   = useGet<Transaction[] | { transactions: Transaction[] }>(
    ['billing-transactions'], '/api/billing/transactions'
  )

  const transactions: Transaction[] = Array.isArray(txRaw) ? txRaw : ((txRaw as any)?.transactions ?? [])

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-semibold text-slate-100">Meu Crédito</h1>

      {/* Balance cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-indigo-600/20 to-indigo-600/5 border border-indigo-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 text-indigo-400 mb-3">
            <DollarSign size={18} />
            <span className="text-xs font-medium uppercase tracking-wide">Saldo disponível</span>
          </div>
          <p className="text-3xl font-bold text-slate-100">{fmtBRL(balance?.credit_balance ?? 0)}</p>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
          <div className="flex items-center gap-2 text-slate-400 mb-3">
            <TrendingDown size={18} />
            <span className="text-xs font-medium uppercase tracking-wide">Custo por minuto</span>
          </div>
          <p className="text-3xl font-bold text-slate-100">{fmtBRL(balance?.cost_per_minute ?? 0)}</p>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
          <div className="flex items-center gap-2 text-slate-400 mb-3">
            <Clock size={18} />
            <span className="text-xs font-medium uppercase tracking-wide">Minutos estimados</span>
          </div>
          <p className="text-3xl font-bold text-slate-100">
            {balance
              ? (() => {
                  const cpm = balance.cost_per_minute || 0
                  const mins = balance.estimated_minutes ?? (cpm > 0 ? balance.credit_balance / cpm : 0)
                  return Math.floor(mins).toLocaleString('pt-BR')
                })()
              : '—'}
          </p>
        </div>
      </div>

      {/* Recharge */}
      <Card>
        <CardHeader title="Recarregar saldo" subtitle="Contate o administrador ou acesse o painel de billing" />
        <CardBody>
          <p className="text-sm text-slate-400">
            Para recarregar seu saldo, entre em contato com o administrador da plataforma ou acesse o painel de administração.
          </p>
        </CardBody>
      </Card>

      {/* Transactions */}
      <Card>
        <CardHeader title="Extrato" subtitle="Últimas transações" />
        <Table
          columns={[
            { key: 'description', header: 'Descrição',  render: r => <span className="text-slate-300">{r.description}</span> },
            { key: 'type',        header: 'Tipo',       render: r => (
              <span className={`text-xs font-medium ${r.type === 'credit' || r.amount > 0 ? 'text-green-400' : 'text-red-400'}`}>
                {r.type === 'credit' || r.amount > 0 ? '+ Crédito' : '− Débito'}
              </span>
            )},
            { key: 'amount',      header: 'Valor',      render: r => (
              <span className={`font-medium ${r.amount > 0 ? 'text-green-400' : 'text-red-400'}`}>
                {fmtBRL(Math.abs(r.amount))}
              </span>
            )},
            { key: 'created_at',  header: 'Data',       render: r => <span className="text-slate-400">{new Date(r.created_at).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}</span> },
          ]}
          data={transactions}
          keyFn={r => r.id}
          empty="Nenhuma transação encontrada."
        />
      </Card>
    </div>
  )
}
