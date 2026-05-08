import { useState } from 'react'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { useGet } from '@/hooks/useApi'
import { api } from '@/api/client'
import toast from 'react-hot-toast'
import { Upload, CheckCircle } from 'lucide-react'
import type { Campaign } from '@/types'

export default function Import() {
  const [file,       setFile]       = useState<File | null>(null)
  const [campaignId, setCampaignId] = useState('')
  const [preview,    setPreview]    = useState<{ columns: string[]; rows: any[][] } | null>(null)
  const [mapping,    setMapping]    = useState<Record<string, string>>({})
  const [importing,  setImporting]  = useState(false)
  const [result,     setResult]     = useState<{ imported: number } | null>(null)

  const { data: campsData } = useGet<{ campaigns: Campaign[] }>(['campaigns'], '/api/campaigns')
  const campaigns = campsData?.campaigns ?? []

  const FIELDS = ['name', 'phone', 'phone2', 'phone3', 'email', 'company', 'notes']

  async function handlePreview() {
    if (!file) return toast.error('Selecione um arquivo')
    const fd = new FormData()
    fd.append('file', file)
    try {
      const r = await api.post('/api/leads/import/preview', fd)
      setPreview(r.data)
      // Auto-map obvious columns
      const auto: Record<string, string> = {}
      r.data.columns.forEach((col: string) => {
        const lower = col.toLowerCase()
        if (lower.includes('nome') || lower === 'name') auto[col] = 'name'
        if (lower.includes('fone') || lower.includes('phone') || lower.includes('tel') || lower.includes('celular')) auto[col] = 'phone'
        if (lower.includes('email') || lower.includes('e-mail')) auto[col] = 'email'
        if (lower.includes('empresa') || lower.includes('company')) auto[col] = 'company'
      })
      setMapping(auto)
    } catch (e: any) { toast.error(e?.response?.data?.error ?? 'Erro ao ler arquivo') }
  }

  async function handleImport() {
    if (!file || !campaignId) return toast.error('Selecione campanha e arquivo')
    setImporting(true)
    const fd = new FormData()
    fd.append('file', file)
    fd.append('campaign_id', campaignId)
    fd.append('mapping', JSON.stringify(mapping))
    try {
      const r = await api.post('/api/leads/import', fd)
      setResult({ imported: r.data.imported ?? r.data.total ?? 0 })
      toast.success(`${r.data.imported ?? r.data.total} leads importados`)
    } catch (e: any) { toast.error(e?.response?.data?.error ?? 'Erro na importação') }
    finally { setImporting(false) }
  }

  if (result) return (
    <div className="p-6 flex items-center justify-center min-h-64">
      <div className="text-center">
        <CheckCircle size={48} className="text-green-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-slate-100">{result.imported} leads importados!</h2>
        <Button className="mt-4" onClick={() => { setResult(null); setFile(null); setPreview(null) }}>
          Nova importação
        </Button>
      </div>
    </div>
  )

  return (
    <div className="p-6 space-y-4 max-w-3xl">
      <h1 className="text-lg font-semibold text-slate-100">Importar Leads</h1>

      <Card>
        <CardHeader title="Arquivo CSV ou XLSX" />
        <CardBody className="space-y-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">Campanha de destino *</label>
            <select value={campaignId} onChange={e => setCampaignId(e.target.value)}>
              <option value="">Selecione uma campanha...</option>
              {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">Arquivo (CSV ou XLSX)</label>
            <div
              className="border-2 border-dashed border-slate-600 rounded-xl p-8 text-center cursor-pointer hover:border-indigo-500 transition-colors"
              onClick={() => document.getElementById('file-input')?.click()}
            >
              <Upload size={24} className="mx-auto mb-2 text-slate-400" />
              {file ? (
                <p className="text-sm text-slate-300">{file.name}</p>
              ) : (
                <p className="text-sm text-slate-400">Clique para selecionar ou arraste o arquivo aqui</p>
              )}
            </div>
            <input id="file-input" type="file" accept=".csv,.xlsx,.xls" className="hidden"
              onChange={e => { setFile(e.target.files?.[0] ?? null); setPreview(null) }} />
          </div>
          <Button variant="secondary" onClick={handlePreview} disabled={!file}>
            Pré-visualizar colunas
          </Button>
        </CardBody>
      </Card>

      {preview && (
        <Card>
          <CardHeader title="Mapeamento de colunas" subtitle="Associe cada coluna do arquivo a um campo do sistema" />
          <CardBody className="space-y-3">
            {preview.columns.map(col => (
              <div key={col} className="flex items-center gap-3">
                <span className="w-40 text-sm text-slate-300 truncate">{col}</span>
                <span className="text-slate-500">→</span>
                <select className="flex-1" value={mapping[col] ?? ''}
                  onChange={e => setMapping(p => ({ ...p, [col]: e.target.value }))}>
                  <option value="">Ignorar</option>
                  {FIELDS.map(f => <option key={f} value={f}>{f}</option>)}
                </select>
              </div>
            ))}

            <div className="border-t border-slate-700 pt-3">
              <p className="text-xs text-slate-400 mb-1">Prévia (primeiras 3 linhas):</p>
              <div className="overflow-x-auto">
                <table className="text-xs text-slate-400 w-full">
                  <thead>
                    <tr>{preview.columns.map(c => <th key={c} className="text-left px-2 py-1 font-medium">{c}</th>)}</tr>
                  </thead>
                  <tbody>
                    {preview.rows.slice(0, 3).map((row, i) => (
                      <tr key={i}>{row.map((cell: any, j: number) => <td key={j} className="px-2 py-1">{cell}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <Button onClick={handleImport} loading={importing} className="w-full justify-center">
              Importar {preview.rows.length} leads
            </Button>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
