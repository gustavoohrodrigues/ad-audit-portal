import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import type { NotificationSummary } from '@/types'

const STATUS_META: Record<string, { label: string; color: string }> = {
  HEALTH_OK: { label: 'HEALTH_OK', color: 'var(--low)' },
  HEALTH_WARN: { label: 'HEALTH_WARN', color: 'var(--medium)' },
  HEALTH_ERR: { label: 'HEALTH_ERR', color: 'var(--critical)' },
}

export function NotificationBell() {
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
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8,
          justifyContent: 'space-between', borderColor: meta.color + '55',
        }}
        title="Saúde e notificações"
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ position: 'relative', fontSize: 15 }}>
            🔔
            {count > 0 && (
              <span style={{
                position: 'absolute', top: -6, right: -8, minWidth: 16, height: 16,
                padding: '0 4px', borderRadius: 10, background: 'var(--grad-red)',
                color: '#fff', fontSize: 10, fontWeight: 800, display: 'flex',
                alignItems: 'center', justifyContent: 'center',
              }}>{count}</span>
            )}
          </span>
          <span style={{ fontSize: 11, fontWeight: 700, color: meta.color }}>{meta.label}</span>
        </span>
      </button>

      {open && (
        <div style={{
          position: 'absolute', bottom: '110%', left: 0, right: 0, zIndex: 40,
          background: 'var(--bg-2)', border: '1px solid var(--border-bright)',
          borderRadius: 10, boxShadow: 'var(--shadow)', maxHeight: 420, overflow: 'auto',
        }}>
          <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between' }}>
            <strong style={{ fontSize: 12 }}>Notificações</strong>
            <span style={{ fontSize: 11, color: meta.color, fontWeight: 700 }}>{meta.label}</span>
          </div>
          {!data?.items.length && <div className="muted" style={{ padding: 16, fontSize: 12 }}>Nada a reportar. 🎉</div>}
          {data?.items.map((n) => (
            <div
              key={n.id}
              onClick={() => { setOpen(false); if (n.link) nav(n.link) }}
              style={{ padding: '9px 12px', borderBottom: '1px solid var(--border)', cursor: 'pointer', display: 'flex', gap: 8 }}
            >
              <span className={`badge ${n.severity}`} style={{ height: 'fit-content' }}>{n.severity}</span>
              <span style={{ fontSize: 12 }}>{n.title}</span>
            </div>
          ))}
          <div
            onClick={() => { setOpen(false); nav('/health') }}
            style={{ padding: '9px 12px', textAlign: 'center', cursor: 'pointer', color: 'var(--accent-2)', fontSize: 12, fontWeight: 600 }}
          >
            Ver painel de Saúde →
          </div>
        </div>
      )}
    </div>
  )
}
