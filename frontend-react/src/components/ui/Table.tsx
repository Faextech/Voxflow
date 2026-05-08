import { type ReactNode } from 'react'

interface Column<T> {
  key:     string
  header:  string
  render?: (row: T) => ReactNode
  width?:  string
}

interface Props<T> {
  columns:  Column<T>[]
  data:     T[]
  keyFn:    (row: T) => string | number
  loading?: boolean
  empty?:   string
}

export function Table<T>({ columns, data, keyFn, loading, empty = 'Nenhum registro encontrado.' }: Props<T>) {
  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            {columns.map(c => (
              <th key={c.key} style={c.width ? { width: c.width } : {}}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr><td colSpan={columns.length} style={{ textAlign: 'center', padding: '32px', color: 'var(--text-secondary)' }}>Carregando...</td></tr>
          )}
          {!loading && data.length === 0 && (
            <tr><td colSpan={columns.length} style={{ textAlign: 'center', padding: '32px', color: 'var(--text-secondary)' }}>{empty}</td></tr>
          )}
          {!loading && data.map(row => (
            <tr key={keyFn(row)}>
              {columns.map(c => (
                <td key={c.key}>
                  {c.render ? c.render(row) : (row as Record<string, ReactNode>)[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
