import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { fmtDate } from '@/lib/format'
import { Badge, Card, Loading } from '@/components/ui'
import type { Lockout } from '@/types'

const STATUS_KIND: Record<string, string> = {
  new: 'high', in_analysis: 'medium', mitigated: 'low', false_positive: 'info', closed: 'info',
}

export function Lockouts() {
  const { data, isLoading } = useQuery({
    queryKey: ['lockouts'],
    queryFn: () => api.get<Lockout[]>('/lockouts'),
    refetchInterval: 30000,
  })

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Investigação de Bloqueios</div>
          <div className="page-sub">Event 4740 · correlação de origem e falhas · sem ação de desbloqueio</div>
        </div>
      </div>
      {isLoading && <Loading />}
      {data && (
        <Card className="table-wrap">
          <table>
            <thead>
              <tr><th>Data/Hora</th><th>Usuário</th><th>DC</th><th>Origem</th><th>Auth</th><th>24h</th><th>Origem 24h</th><th>Status</th></tr>
            </thead>
            <tbody>
              {data.map((l) => (
                <tr key={l.id}>
                  <td className="mono">{fmtDate(l.lockout_time_utc)}</td>
                  <td><Link to={`/lockouts/${l.id}`} className="mono">{l.target_username}</Link></td>
                  <td className="mono muted">{l.domain_controller}</td>
                  <td className="mono">{l.caller_computer || '—'}</td>
                  <td>{l.auth_type || '—'}</td>
                  <td>{l.lockouts_24h}</td>
                  <td>{l.lockouts_same_source}</td>
                  <td><Badge kind={STATUS_KIND[l.status] || 'info'}>{l.status}</Badge></td>
                </tr>
              ))}
              {!data.length && <tr><td colSpan={8} className="muted">Nenhum bloqueio registrado.</td></tr>}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
