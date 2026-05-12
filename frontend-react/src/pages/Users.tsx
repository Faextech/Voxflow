import { useGet } from '@/hooks/useApi'
import { Card } from '@/components/ui/Card'
import { Table } from '@/components/ui/Table'
import { Badge } from '@/components/ui/Badge'
import type { User } from '@/types'

export default function Users() {
  // API returns flat array OR { users: [...] }
  const { data: raw, isLoading } = useGet<User[] | { users: User[] }>(['users'], '/api/users')
  const users: User[] = Array.isArray(raw) ? raw : ((raw as Record<string, unknown>)?.users as User[] ?? [])

  const roleColor: Record<string, 'green' | 'indigo' | 'yellow' | 'slate'> = {
    admin:      'indigo',
    supervisor: 'yellow',
    operator:   'slate',
    superadmin: 'green',
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div className="page-header">
        <div>
          <h1>Usuários</h1>
          <p>{users.length} usuários cadastrados</p>
        </div>
      </div>

      <Card>
        <Table
          columns={[
            { key: 'name',       header: 'Nome',       render: r => <span style={{ fontWeight: 500 }}>{r.name}</span> },
            { key: 'email',      header: 'Email',      render: r => <span style={{ color: 'var(--text-secondary)' }}>{r.email}</span> },
            { key: 'role',       header: 'Papel',      render: r => <Badge label={r.role} color={roleColor[r.role] ?? 'slate'} /> },
            { key: 'created_at', header: 'Cadastrado', render: r => <span style={{ color: 'var(--text-secondary)' }}>{new Date(r.created_at).toLocaleDateString('pt-BR')}</span> },
          ]}
          data={users}
          keyFn={r => r.id}
          loading={isLoading}
        />
      </Card>
    </div>
  )
}
