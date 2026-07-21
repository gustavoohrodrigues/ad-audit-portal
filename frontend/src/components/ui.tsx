import { ReactNode } from 'react'
import type { Severity } from '@/types'

export function Badge({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={`badge ${kind}`}>{children}</span>
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge kind={severity}>{severity}</Badge>
}

export function Card({ title, children, className }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <div className={`card ${className || ''}`}>
      {title && <h3>{title}</h3>}
      {children}
    </div>
  )
}

export function Kpi({ label, value, tone }: { label: string; value: number | string; tone?: string }) {
  return (
    <div className="card">
      <div className={`kpi-value ${tone || ''}`}>{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  )
}

export function Loading({ text = 'Carregando…' }: { text?: string }) {
  return <div className="loading">{text}</div>
}

export function StatusDot({ status }: { status: string }) {
  return <span className={`status-dot ${status}`} />
}
