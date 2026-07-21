import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { fmtDate } from '@/lib/format'
import { Badge, Card, Loading } from '@/components/ui'
import type { NotificationRow } from '@/types'

export function Notifications() {
  const { data, isLoading } = useQuery({
    queryKey: ['notif-history'],
    queryFn: () => api.get<{ items: NotificationRow[] }>('/notifications/history'),
    refetchInterval: 30000,
  })

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Centro de Notificações</div>
          <div className="page-sub">Histórico de ações ativas (e-mail, ChatOps, WinRM) · auditado</div>
        </div>
      </div>
      {isLoading && <Loading />}
      {data && (
        <Card className="table-wrap">
          <table>
            <thead>
              <tr><th>Hora</th><th>Canal</th><th>Alvo</th><th>Assunto</th><th>Solicitante</th><th>Ticket</th><th>Status</th></tr>
            </thead>
            <tbody>
              {data.items.map((n) => (
                <tr key={n.correlation_id}>
                  <td className="mono">{fmtDate(n.time)}</td>
                  <td><Badge kind="info">{n.channel}</Badge></td>
                  <td className="mono">{n.target || '—'}</td>
                  <td>{n.subject || '—'}</td>
                  <td className="mono muted">{n.requested_by} ({n.role})</td>
                  <td className="mono muted">{n.ticket || '—'}</td>
                  <td>
                    {n.status === 'sent'
                      ? <Badge kind="low">enviado</Badge>
                      : <Badge kind="critical" >falha</Badge>}
                    {n.error && <div className="muted" style={{ fontSize: 11 }}>{n.error}</div>}
                  </td>
                </tr>
              ))}
              {!data.items.length && <tr><td colSpan={7} className="muted">Nenhuma notificação enviada ainda.</td></tr>}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
