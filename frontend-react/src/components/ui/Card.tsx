import { type ReactNode } from 'react'

interface CardProps  { children: ReactNode; className?: string }
interface HeaderProps { title: string; subtitle?: string; action?: ReactNode }

export function Card({ children, className = '' }: CardProps) {
  return <div className={`panel ${className}`}>{children}</div>
}

export function CardHeader({ title, subtitle, action }: HeaderProps) {
  return (
    <div className="panel-header">
      <div>
        <h3>{title}</h3>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  )
}

export function CardBody({ children, className = '' }: CardProps) {
  return <div className={`panel-body ${className}`}>{children}</div>
}
