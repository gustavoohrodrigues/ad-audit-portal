import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { fmtDate, eventLabel } from '@/lib/format'
import { Badge, Card, Loading, SeverityBadge } from '@/components/ui'
import { useAuth } from '@/hooks/useAuth'
import type { EventRow } from '@/types'

interface Paginated { total: number; page: number; page_size: number; items: EventRow[] }

export function Events() {
  const { can } = useAuth()
  const [q, setQ] = useState('')
  const [type, setType] = useState('')
  const [page, setPage] = useState(1)
  const [raw, setRaw] = useState<{ id: number; json: unknown } | null>(null)

  const params = new URLSearchParams({ page: String(page), page_size: '50' })
  if (q) params.set('q', q)
  if (type) params.set('event_type', type)

  const { data, isLoading } = useQuery({
    queryKey: ['events', q, type, page],
    queryFn: () => api.get<Paginated>(`/events?${params.toString()}`),
  })

  async function openRaw(id: number) {
    const ev = await api.get<EventRow & { raw_event_json: unknown }>(`/events/${id}/raw`)
    setRaw({ id, json: ev.raw_event_json })
  }

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Eventos Normalizados</div>
          <div className="page-sub">Consulta e filtro · JSON bruto restrito a security_analyst/admin</div>
        </div>
      </div>
      <Card>
        <form className="row" onSubmit={(e) => { e.preventDefault(); setPage(1) }}>
          <input placeholder="usuário / SID / computador…" value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: 1 }} />
          <select value={type} onChange={(e) => setType(e.target.value)} style={{ width: 240 }}>
            <option value="">Todos os tipos</option>
            {['account_lockout', 'failed_logon', 'password_reset', 'password_change', 'group_member_added', 'account_changed'].map((t) => (
              <option key={t} value={t}>{eventLabel(t)}</option>
            ))}
          </select>
          <button className="primary" type="submit">Filtrar</button>
        </form>
      </Card>

      {isLoading && <Loading />}
      {data && (
        <Card className="table-wrap" title={`${data.total} evento(s)`}>
          <table>
            <thead><tr><th>Hora</th><th>Tipo</th><th>Sev</th><th>Risco</th><th>Alvo</th><th>DC</th><th>Origem</th><th></th></tr></thead>
            <tbody>
              {data.items.map((e) => (
                <tr key={e.id}>
                  <td className="mono">{fmtDate(e.event_time_utc)}</td>
                  <td>{eventLabel(e.event_type)} {e.is_privileged_target && <Badge kind="priv">priv</Badge>}</td>
                  <td><SeverityBadge severity={e.severity} /></td>
                  <td>{e.risk_score}</td>
                  <td className="mono">{e.target_username || '—'}</td>
                  <td className="mono muted">{e.domain_controller}</td>
                  <td className="mono">{e.caller_computer || e.source_ip || '—'}</td>
                  <td>{can('event:raw_read') && <button onClick={() => openRaw(e.id)} style={{ padding: '4px 8px' }}>JSON</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row" style={{ marginTop: 12 }}>
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>← Anterior</button>
            <span className="muted">Página {data.page}</span>
            <button disabled={data.page * data.page_size >= data.total} onClick={() => setPage((p) => p + 1)}>Próxima →</button>
          </div>
        </Card>
      )}

      {raw && (
        <Card title={`JSON bruto · evento ${raw.id} (acesso auditado)`}>
          <button onClick={() => setRaw(null)} style={{ float: 'right' }}>Fechar</button>
          <pre className="mono" style={{ whiteSpace: 'pre-wrap', fontSize: 12, maxHeight: 380, overflow: 'auto' }}>
            {JSON.stringify(raw.json, null, 2)}
          </pre>
        </Card>
      )}
    </>
  )
}
