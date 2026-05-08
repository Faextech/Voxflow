import { type ButtonHTMLAttributes, type ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'accent' | 'danger' | 'ghost'
type Size    = 'sm' | 'md' | 'lg'

const variantClass: Record<Variant, string> = {
  primary:   'btn-primary',
  secondary: 'btn-secondary',
  accent:    'btn-accent',
  danger:    'btn-danger',
  ghost:     'btn-ghost',
}
const sizeClass: Record<Size, string> = {
  sm: 'btn-sm', md: '', lg: 'btn-lg',
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  children: ReactNode
}

export function Button({ variant = 'primary', size = 'md', loading, children, className = '', disabled, ...rest }: Props) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`btn ${variantClass[variant]} ${sizeClass[size]} ${className}`}
    >
      {loading && <span className="spinner" />}
      {children}
    </button>
  )
}
