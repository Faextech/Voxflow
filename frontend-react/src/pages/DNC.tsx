import { useState } from 'react'
import { useGet, useMut } from '@/hooks/useApi'
import { Card } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Plus, Download, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '@/api/client'
import toast from 'react-hot-toast'
import type { DncEntry } from '@/types'

export default function DNC() {
  const [page,    setPage]    = useState(1)
  const [search,  setSearch]  = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [phone,   setPhone]   = useState('')
  const [reason,  setReason]  = useState('')
  const [bulk,    setBulk]    = useState('')

  const { data, isLoading, refetch } = useGet<{ items: DncEntry[]; total: number; pages: number }>(
    ['dnc', String(page), search],
    `/api/dnc?page=${page}&per_page=50&q=${search}`,
    undefined,
    { keepPreviousData: true }
  )

  const add    = useMut('post',   '/api/dnc',                              [['dnc']])
  const remove = useMut('delete', (v: { id: number }) => `/api/dnc/${v.id}`, [['dnc']])

  async function handleAdd() {
    try {
      await add.mutateAsync({ phone, reason })
      toast.success('Adicionado à DNC'); setPhone(''); setReason(''); refetch()
    } catch (e: any) { toast.error(e?.response?.data?.error ?? 'Erro') }
  }

  async function handleBulk() {
    const phones = bulk.split('\n').map(s => s.trim()).filter(Boolean)
    if (!phones.length) return toast.error('Nenhum número encontrado')
    try {
      await add.mutateAsync({ phones } as any)
      toast.success(`${phones.length} números importados`); setBulk(''); setShowAdd(false); refetch()
    } catch (e: any) { toast.error(e?.response?.data?.error ?? 'Erro') }
  }

  async function handleDelete(id: number) {
    try { await remove.mutateAsync({ id }); toast.success('Removido'); refetch() }
    catch { toast.error('Erro ao remover') }
  }

  async function exportCSV() {
    try {
      const res = await api.get('/api/analytics/export/dnc', { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a'); a.href = url; a.download = 'dnc.csv'; a.click()
      URL.revokeObjectURL(url)
    } catch { toast.error('Erro ao exportar') }
  }

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const pages = data?.pages ?? 1

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Lista DNC</h1>
          <p className="text-sm text-slate-400">{total} números bloqueados</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={exportCSV}><Download size={14} /> Exportar</Button>
          <Button onClick={() => setShowAdd(true)}><Plus size={15} /> Adicionar</Button>
        </div>
      </div>

      <input
        placeholder="Buscar por número..."
        value={search}
        onChange={e => { setSearch(e.target.value); setPage(1) }}
      />

      <Card>
        <Table
          columns={[
            { key: 'phone',      header: 'Telefone',  render: r => <span className="font-medium text-slate-200">{r.phone}</span> },
            { key: 'reason',     header: 'Motivo',    render: r => <span className="text-slate-400">{r.reason ?? '—'}</span> },
            { key: 'created_at', header: 'Adicionado',render: r => <span className="text-slate-400">{new Date(r.created_at).toLocaleDateString('pt-BR')}</span> },
            { key: 'del', header: '', width: '50px', render: r => (
              <button onClick={() => handleDelete(r.id)} className="text-slate-500 hover:text-red-400 p-1 transition-colors">
                <Trash2 size={14} />
              </button>
            )},
          ]}
          data={items}
          keyFn={r => r.id}
          loading={isLoading}
        />
        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700">
            <span className="text-xs text-slate-400">Página {page} de {pages}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" disabled={page <= 1}    onClick={() => setPage(p => p - 1)}><ChevronLeft size={14} /> Anterior</Button>
              <Button size="sm" variant="ghost" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>Próxima <ChevronRight size={14} /></Button>
            </div>
          </div>
        )}
      </Card>

      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Adicionar à DNC" size="md">
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">Número único</label>
            <div className="flex gap-2">
              <input value={phone} onChange={e => setPhone(e.target.value)} placeholder="+5511999990000" />
              <Button onClick={handleAdd} loading={add.isPending}>Adicionar</Button>
            </div>
          </div>
          <div className="border-t border-slate-700 pt-4">
            <label className="block text-xs text-slate-400 mb-1.5">Importação em massa (um número por linha)</label>
            <textarea rows={6} value={bulk} onChange={e => setBulk(e.target.value)} placeholder={"+5511999990000\n+5511888880000"} />
            <Button className="mt-2 w-full justify-center" variant="secondary" onClick={handleBulk}>
              Importar lista
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
