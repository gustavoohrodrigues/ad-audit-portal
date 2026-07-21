import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { fmtDate } from '@/lib/format'
import { Card, Loading, SeverityBadge } from '@/components/ui'
import type { Alert } from '@/types'

export function Alerts() {
  const { data, isLoading } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api.get<Alert[]>('/alerts'),
    refetchInterval: 30000,
  })

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Alertas</div>
          <div className="page-sub">Motor de risco · deduplicação e supressão ativas</div>
        </div>
      </div>
      {isLoading && <Loading />}
      {data && (
        <Card className="table-wrap">
          <table>
            <thead><tr><th>Criado</th><th>Severidade</th><th>Risco</th><th>Título</th><th>Alvo</th><th>Status</th></tr></thead>
            <tbody>
              {data.map((a) => (
                <tr key={a.id}>
                  <td className="mono">{fmtDate(a.created_at)}</td>
                  <td><SeverityBadge severity={a.severity} /></td>
                  <td>{a.risk_score}</td>
                  <td>{a.title}</td>
                  <td className="mono">{a.target_username || '—'}</td>
                  <td className="muted">{a.status}</td>
                </tr>
              ))}
              {!data.length && <tr><td colSpan={6} className="muted">Nenhum alerta ativo.</td></tr>}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
