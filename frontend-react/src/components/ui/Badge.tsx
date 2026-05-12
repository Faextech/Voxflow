/**
 * Badge component and status badge helper.
 * Note: statusBadge is co-located here for convenience.
 * ESLint react-refresh is configured to allow mixed exports.
 */

export type { }

type Color = 'green' | 'red' | 'yellow' | 'blue' | 'slate' | 'indigo'

const cls: Record<Color, string> = {
  green:  'badge-green',
  red:    'badge-red',
  yellow: 'badge-yellow',
  blue:   'badge-blue',
  slate:  'badge-slate',
  indigo: 'badge-indigo',
}

const dotColor: Record<Color, string> = {
  green:  '#16a34a',
  red:    '#dc2626',
  yellow: '#d97706',
  blue:   '#2563eb',
  slate:  '#64748b',
  indigo: '#6366f1',
}

interface Props { label: string; color?: Color; dot?: boolean }

export function Badge({ label, color = 'slate', dot = false }: Props) {
  return (
    <span className={`badge ${cls[color]}`}>
      {dot && <span className="badge-dot" style={{ background: dotColor[color] }} />}
      {label}
    </span>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function statusBadge(status: string) {
  const map: Record<string, { label: string; color: Color }> = {
    active:          { label: 'Ativo',      color: 'green'  },
    running:         { label: 'Rodando',    color: 'green'  },
    paused:          { label: 'Pausado',    color: 'yellow' },
    stopped:         { label: 'Parado',     color: 'slate'  },
    finished:        { label: 'Concluído',  color: 'blue'   },
    idle:            { label: 'Livre',      color: 'slate'  },
    answered:        { label: 'Atendida',   color: 'green'  },
    no_answer:       { label: 'Não atend.', color: 'yellow' },
    failed:          { label: 'Falhou',     color: 'red'    },
    new:             { label: 'Novo',       color: 'indigo' },
    called:          { label: 'Chamado',    color: 'blue'   },
    pending:         { label: 'Pendente',   color: 'yellow' },
    pending_manual:  { label: 'Manual',     color: 'yellow' },
    sent:            { label: 'Enviado',    color: 'green'  },
    converted:       { label: 'Convertido', color: 'green'  },
    online:          { label: 'Online',     color: 'green'  },
    offline:         { label: 'Offline',    color: 'slate'  },
    busy:            { label: 'Ocupado',    color: 'yellow' },
    done:            { label: 'Concluído',  color: 'green'  },
    skipped:         { label: 'Pulado',     color: 'slate'  },
  }
  const cfg = map[status] ?? { label: status, color: 'slate' as Color }
  return <Badge {...cfg} dot />
}
