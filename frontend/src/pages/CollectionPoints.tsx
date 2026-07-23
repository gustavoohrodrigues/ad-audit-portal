import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { fmtDate, relative } from '@/lib/format'
import { Badge, Card, Loading } from '@/components/ui'
import { Icon } from '@/components/icons'

interface Source {
  name: string; connector_type: string; endpoint?: string; enabled: boolean; status: string
  events_ingested: number; errors_count: number; last_error?: string
  last_event_at?: string; last_heartbeat_at?: string; last_event_age_s?: number; health: string
}
interface Checkpoint {
  source: string; channel: string; last_event_record_id?: number
  last_event_time_utc?: string; updated_at?: string; lag_seconds?: number
}
interface DC {
  dc: string; events_24h: number; events_7d: number; last_event?: string
  event_types: number; last_event_age_s?: number; status: string
}
interface Data {
  summary: { sources: number; dcs_total: number; dcs_active: number; dcs_stale: number; events_24h: number; total_errors: number }
  sources: Source[]; checkpoints: Checkpoint[]; domain_controllers: DC[]
}

const ST: Record<string, { c: string; label: string }> = {
  active: { c: 'var(--low)', label: 'Ativo' },
  idle: { c: 'var(--medium)', label: 'Ocioso' },
  stale: { c: 'var(--critical)', label: 'Parado' },
  unknown: { c: 'var(--text-2)', label: 'Sem dados' },
  healthy: { c: 'var(--low)', label: 'Saudável' },
  degraded: { c: 'var(--medium)', label: 'Degradado' },
  down: { c: 'var(--critical)', label: 'Fora do ar' },
}

function Dot({ status }: { status: string }) {
  const s = ST[status] || ST.unknown
  return <span style={{ width: 10, height: 10, borderRadius: '50%', background: s.c, boxShadow: `0 0 8px ${s.c}`, display: 'inline-block', flexShrink: 0 }} />
}

export function CollectionPoints() {
  const { data, isLoading } = useQuery({
    queryKey: ['collection-points'],
    queryFn: () => api.get<Data>('/monitoring/collection-points'),
    refetchInterval: 20000,
  })
  if (isLoading || !data) return <Loading />
  const s = data.summary
  const maxDc = Math.max(1, ...data.domain_controllers.map((d) => d.events_7d))

  return (
    <>
      <div className="hero">
        <div className="hero-scan" />
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Pontos de <span className="accent-text">Coleta</span></h1>
            <div className="page-sub" style={{ marginTop: 4 }}>
              Conectores, checkpoints e atividade de ingestão por Domain Controller · atualização automática
            </div>
          </div>
          <span className="live-dot">Ao vivo</span>
        </div>
      </div>

      <div className="grid kpi-row">
        <div className="card kpi-hot"><div className="kpi-value">{s.dcs_active}</div><div className="kpi-label">DCs ativos (1h)</div></div>
        <div className="card kpi-hot"><div className={`kpi-value ${s.dcs_stale > 0 ? 'critical' : ''}`}>{s.dcs_stale}</div><div className="kpi-label">DCs parados</div></div>
        <div className="card kpi-hot"><div className="kpi-value">{s.events_24h.toLocaleString('pt-BR')}</div><div className="kpi-label">Eventos coletados (24h)</div></div>
        <div className="card kpi-hot"><div className="kpi-value">{s.sources}</div><div className="kpi-label">Fontes/conectores</div></div>
        <div className="card kpi-hot"><div className={`kpi-value ${s.total_errors > 0 ? 'high' : ''}`}>{s.total_errors}</div><div className="kpi-label">Erros acumulados</div></div>
      </div>

      {/* Atividade por Domain Controller */}
      <Card title={`Atividade por Domain Controller (${data.domain_controllers.length})`} className="table-wrap">
        {!data.domain_controllers.length && <div className="muted">Nenhum evento nos últimos 7 dias. Verifique os conectores/coletor.</div>}
        {data.domain_controllers.length > 0 && (
          <table>
            <thead><tr><th>Status</th><th>Domain Controller</th><th>Eventos 24h</th><th>Eventos 7d</th><th>Tipos</th><th>Último evento</th><th></th></tr></thead>
            <tbody>
              {data.domain_controllers.map((d) => (
                <tr key={d.dc}>
                  <td><div className="row" style={{ gap: 7 }}><Dot status={d.status} /> <span style={{ fontSize: 12 }}>{(ST[d.status] || ST.unknown).label}</span></div></td>
                  <td className="mono">{d.dc}</td>
                  <td>{d.events_24h.toLocaleString('pt-BR')}</td>
                  <td>
                    <div className="row" style={{ gap: 8 }}>
                      <span className="mono muted" style={{ width: 60 }}>{d.events_7d.toLocaleString('pt-BR')}</span>
                      <div className="riskbar-track" style={{ flex: 1, minWidth: 80 }}><div className="riskbar-fill" style={{ width: `${(d.events_7d / maxDc) * 100}%` }} /></div>
                    </div>
                  </td>
                  <td className="muted">{d.event_types}</td>
                  <td className="mono muted">{relative(d.last_event)}</td>
                  <td className="muted" style={{ fontSize: 11 }}>{fmtDate(d.last_event)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 16 }}>
        {/* Fontes / conectores */}
        <Card title="Fontes / Conectores" className="table-wrap">
          {!data.sources.length && <div className="muted">Nenhuma fonte registrada ainda. O coletor cria a fonte na primeira ingestão.</div>}
          {data.sources.length > 0 && (
            <table>
              <thead><tr><th>Status</th><th>Fonte</th><th>Tipo</th><th>Ingeridos</th><th>Erros</th><th>Últ. evento</th></tr></thead>
              <tbody>
                {data.sources.map((src) => (
                  <tr key={src.name}>
                    <td><div className="row" style={{ gap: 7 }}><Dot status={src.health} /></div></td>
                    <td className="mono">{src.name}{!src.enabled && <Badge kind="low">off</Badge>}</td>
                    <td className="muted">{src.connector_type}</td>
                    <td>{src.events_ingested.toLocaleString('pt-BR')}</td>
                    <td>{src.errors_count > 0 ? <Badge kind="high">{src.errors_count}</Badge> : <span className="muted">0</span>}</td>
                    <td className="mono muted">{relative(src.last_event_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {/* Checkpoints */}
        <Card title="Checkpoints de coleta" className="table-wrap">
          {!data.checkpoints.length && <div className="muted">Sem checkpoints. O coletor grava o progresso por fonte/canal aqui.</div>}
          {data.checkpoints.length > 0 && (
            <table>
              <thead><tr><th>Fonte</th><th>Canal</th><th>Último RecordID</th><th>Último evento</th></tr></thead>
              <tbody>
                {data.checkpoints.map((c) => (
                  <tr key={`${c.source}-${c.channel}`}>
                    <td className="mono">{c.source}</td>
                    <td className="muted">{c.channel}</td>
                    <td className="mono">{c.last_event_record_id?.toLocaleString('pt-BR') ?? '—'}</td>
                    <td className="mono muted">{relative(c.last_event_time_utc)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      <div className="muted" style={{ fontSize: 11, marginTop: 12, display: 'flex', gap: 7, alignItems: 'center' }}>
        <Icon name="dot" size={14} /> Um DC é considerado <b>ativo</b> com evento na última hora, <b>ocioso</b> em até 24h e <b>parado</b> além disso.
      </div>
    </>
  )
}
