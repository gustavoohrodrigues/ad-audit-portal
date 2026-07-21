import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { fmtDate } from '@/lib/format'
import { Badge, Card, Loading, StatusDot } from '@/components/ui'

interface Connectors {
  mode: string
  sources: { name: string; type: string; enabled: boolean; status: string; last_event_at?: string; events_ingested: number; errors_count: number; last_error?: string }[]
}
interface AuditLogs {
  items: { time: string; actor: string; role?: string; action: string; resource?: string; ip?: string; success: boolean }[]
}

export function Admin() {
  const connectors = useQuery({ queryKey: ['connectors'], queryFn: () => api.get<Connectors>('/admin/connectors') })
  const audit = useQuery({ queryKey: ['audit'], queryFn: () => api.get<AuditLogs>('/admin/audit-logs') })

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Administração</div>
          <div className="page-sub">Fontes de eventos · auditoria interna</div>
        </div>
      </div>

      <Card title={`Fontes de eventos (modo: ${connectors.data?.mode || '…'})`} className="table-wrap">
        {connectors.isLoading && <Loading />}
        <table>
          <thead><tr><th>Fonte</th><th>Tipo</th><th>Status</th><th>Último evento</th><th>Ingeridos</th><th>Erros</th></tr></thead>
          <tbody>
            {(connectors.data?.sources || []).map((s) => (
              <tr key={s.name}>
                <td className="mono">{s.name}</td>
                <td>{s.type}</td>
                <td><StatusDot status={s.status} />{s.status}</td>
                <td className="mono muted">{fmtDate(s.last_event_at)}</td>
                <td>{s.events_ingested}</td>
                <td className={s.errors_count > 0 ? '' : 'muted'}>{s.errors_count}</td>
              </tr>
            ))}
            {!connectors.data?.sources.length && <tr><td colSpan={6} className="muted">Nenhuma fonte registrada.</td></tr>}
          </tbody>
        </table>
      </Card>

      <Card title="Auditoria interna" className="table-wrap">
        {audit.isLoading && <Loading />}
        <table>
          <thead><tr><th>Hora</th><th>Ator</th><th>Perfil</th><th>Ação</th><th>Recurso</th><th>IP</th><th></th></tr></thead>
          <tbody>
            {(audit.data?.items || []).map((a, i) => (
              <tr key={i}>
                <td className="mono">{fmtDate(a.time)}</td>
                <td className="mono">{a.actor}</td>
                <td className="muted">{a.role || '—'}</td>
                <td>{a.action}</td>
                <td className="mono muted">{a.resource || '—'}</td>
                <td className="mono muted">{a.ip || '—'}</td>
                <td>{a.success ? <Badge kind="low">ok</Badge> : <Badge kind="critical">falha</Badge>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  )
}
