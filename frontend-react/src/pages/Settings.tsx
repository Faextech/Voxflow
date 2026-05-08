import { useState, useEffect } from 'react'
import { useGet, useMut } from '@/hooks/useApi'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import toast from 'react-hot-toast'
import { api } from '@/api/client'

export default function Settings() {
  const [companyForm, setCompanyForm] = useState({ name: '', segment: '' })
  const [savingComp,  setSavingComp]  = useState(false)
  const [testing,     setTesting]     = useState(false)

  useEffect(() => {
    api.get('/api/settings/company').then(r => {
      setCompanyForm({ name: r.data.name ?? '', segment: r.data.segment ?? '' })
    }).catch(() => {})
  }, [])

  async function saveCompany() {
    setSavingComp(true)
    try {
      await api.put('/api/settings/company', companyForm)
      toast.success('Configurações salvas')
    } catch (e: any) {
      toast.error(e?.response?.data?.error ?? 'Erro')
    } finally { setSavingComp(false) }
  }

  async function testTwilio() {
    setTesting(true)
    try {
      const r = await api.post('/api/settings/twilio/test')
      toast.success(`Twilio OK — ${r.data.account_name} (${r.data.status})`)
    } catch (e: any) {
      toast.error(e?.response?.data?.error ?? 'Erro na conexão Twilio')
    } finally { setTesting(false) }
  }

  return (
    <div className="p-6 space-y-4 max-w-2xl">
      <h1 className="text-lg font-semibold text-slate-100">Configurações</h1>

      {/* Company */}
      <Card>
        <CardHeader title="Dados da empresa" />
        <CardBody className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Nome da empresa</label>
              <input
                value={companyForm.name}
                onChange={e => setCompanyForm(p => ({ ...p, name: e.target.value }))}
                placeholder="Minha Empresa Ltda"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Segmento</label>
              <input
                value={companyForm.segment}
                onChange={e => setCompanyForm(p => ({ ...p, segment: e.target.value }))}
                placeholder="Ex: Tecnologia, Saúde..."
              />
            </div>
          </div>
          <Button onClick={saveCompany} loading={savingComp}>Salvar</Button>
        </CardBody>
      </Card>

      {/* Twilio test */}
      <Card>
        <CardHeader title="Integração Twilio" subtitle="Verifique se as credenciais estão funcionando" />
        <CardBody>
          <p className="text-sm text-slate-400 mb-4">
            As credenciais Twilio são configuradas pelo painel de administração. Utilize o botão abaixo para validar a conexão.
          </p>
          <Button variant="secondary" onClick={testTwilio} loading={testing}>
            Testar conexão Twilio
          </Button>
        </CardBody>
      </Card>

      {/* Danger zone */}
      <Card>
        <CardHeader title="Zona de perigo" />
        <CardBody>
          <p className="text-sm text-slate-400 mb-4">
            Apagar todos os dados da empresa (leads, chamadas, campanhas). Esta ação é irreversível.
          </p>
          <Button variant="danger" onClick={() => toast.error('Use o painel de configurações web para esta ação.')}>
            Apagar todos os dados
          </Button>
        </CardBody>
      </Card>
    </div>
  )
}
