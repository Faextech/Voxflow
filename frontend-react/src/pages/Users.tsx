import { useGet } from '@/hooks/useApi'
import { Card } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { Badge } from '@/components/ui/Badge'
import type { User } from '@/types'

export default function Users() {
  // API returns flat array OR { users: [...] }
  const { data: raw, isLoading } = useGet<User[] | { users: User[] }>(['users'], '/api/users')
  const users: User[] = Array.isArray(raw) ? raw : ((raw as any)?.users ?? [])

  const roleColor: Record<string, 'green' | 'indigo' | 'yellow' | 'slate'> = {
    admin:      'indigo',
    supervisor: 'yellow',
    operator:   'slate',
    superadmin: 'green',
  }

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">Usuários</h1>
        <p className="text-sm text-slate-400">{users.length} usuários cadastrados</p>
      </div>

      <Card>
        <Table
          columns={[
            { key: 'name',       header: 'Nome',       render: r => <span className="font-medium text-slate-200">{r.name}</span> },
            { key: 'email',      header: 'Email',      render: r => <span className="text-slate-400">{r.email}</span> },
            { key: 'role',       header: 'Papel',      render: r => <Badge label={r.role} color={roleColor[r.role] ?? 'slate'} /> },
            { key: 'created_at', header: 'Cadastrado', render: r => <span className="text-slate-400">{new Date(r.created_at).toLocaleDateString('pt-BR')}</span> },
          ]}
          data={users}
          keyFn={r => r.id}
          loading={isLoading}
        />
      </Card>
    </div>
  )
}
