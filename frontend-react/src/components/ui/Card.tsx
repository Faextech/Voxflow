import { type ReactNode, type CSSProperties } from 'react'

interface CardProps  { children: ReactNode; className?: string; style?: CSSProperties }
interface HeaderProps { title: string; subtitle?: string; action?: ReactNode }
interface BodyProps  { children: ReactNode; className?: string; style?: CSSProperties }

export function Card({ children, className = '', style }: CardProps) {
  return <div className={`panel ${className}`} style={style}>{children}</div>
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

export function CardBody({ children, className = '', style }: BodyProps) {
  return <div className={`panel-body ${className}`} style={style}>{children}</div>
}
