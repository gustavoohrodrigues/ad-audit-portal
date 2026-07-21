import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { Icon } from '@/components/icons'
import type { NotificationSummary } from '@/types'

const STATUS_META: Record<string, { label: string; color: string }> = {
  HEALTH_OK: { label: 'HEALTH_OK', color: 'var(--low)' },
  HEALTH_WARN: { label: 'HEALTH_WARN', color: 'var(--medium)' },
  HEALTH_ERR: { label: 'HEALTH_ERR', color: 'var(--critical)' },
}

export function NotificationBell({ collapsed = false }: { collapsed?: boolean }) {
  const [open, setOpen] = useState(false)
  const nav = useNavigate()
  const { data } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.get<NotificationSummary>('/monitoring/notifications'),
    refetchInterval: 20000,
  })

  const meta = STATUS_META[data?.status || 'HEALTH_OK']
  const count = data?.count || 0

  return (
    <div style={{ position: 'relative' }}>
      <button className="nav-item as-button" onClick={() => setOpen((o) => !o)} title="Saúde e notificações">
        <span style={{ position: 'relative', display: 'inline-flex' }}>
          <Icon name="bell" size={18} style={{ color: meta.color }} />
          {count > 0 && (
            <span className="badge-count">{count > 99 ? '99+' : count}</span>
          )}
        </span>
        {!collapsed && <span className="nav-label" style={{ color: meta.color, fontWeight: 700, fontSize: 11 }}>{meta.label}</span>}
      </button>

      {open && (
        <div className="notif-panel">
          <div className="notif-head">
            <strong style={{ fontSize: 12 }}>Notificações</strong>
            <span style={{ fontSize: 11, color: meta.color, fontWeight: 700 }}>{meta.label}</span>
          </div>
          {!data?.items.length && <div className="muted" style={{ padding: 16, fontSize: 12 }}>Nada a reportar.</div>}
          {data?.items.map((n) => (
            <div key={n.id} className="notif-item" onClick={() => { setOpen(false); if (n.link) nav(n.link) }}>
              <span className={`badge ${n.severity}`} style={{ height: 'fit-content' }}>{n.severity}</span>
              <span style={{ fontSize: 12 }}>{n.title}</span>
            </div>
          ))}
          <div className="notif-foot" onClick={() => { setOpen(false); nav('/health') }}>
            Ver painel de Saúde
          </div>
        </div>
      )}
    </div>
  )
}
