import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Badge, Card, Loading } from '@/components/ui'

interface CapacityData {
  database: {
    size_human: string
    counts: Record<string, number | null>
    top_tables: { table: string; size_human: string; rows: number }[]
    unused_indexes: { table: string; index: string }[]
  }
  redis: Record<string, string | number>
  celery_queues: Record<string, number | null>
  config: Record<string, unknown>
}

export function Capacity() {
  const { data, isLoading } = useQuery({
    queryKey: ['capacity'],
    queryFn: () => api.get<CapacityData>('/admin/capacity'),
    refetchInterval: 30000,
  })

  if (isLoading || !data) return <Loading />
  const hits = Number(data.redis.keyspace_hits || 0)
  const misses = Number(data.redis.keyspace_misses || 0)
  const hitRatio = hits + misses > 0 ? ((hits / (hits + misses)) * 100).toFixed(1) : '—'
  const queues = Object.entries(data.celery_queues).filter(([, v]) => v && v > 0)

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Capacidade & Performance</div>
          <div className="page-sub">Métricas operacionais do banco, Redis e filas · atualização automática</div>
        </div>
      </div>

      <div className="grid kpi-row">
        <div className="card kpi-hot"><div className="kpi-value">{data.database.size_human}</div><div className="kpi-label">Tamanho do banco</div></div>
        <div className="card kpi-hot"><div className="kpi-value">{String(data.redis.used_memory_human || '—')}</div><div className="kpi-label">Redis em uso</div></div>
        <div className="card kpi-hot"><div className="kpi-value">{data.redis.keys ?? '—'}</div><div className="kpi-label">Chaves Redis</div></div>
        <div className="card kpi-hot"><div className={`kpi-value ${Number(hitRatio) < 50 ? 'medium' : 'low'}`}>{hitRatio}%</div><div className="kpi-label">Cache hit ratio (Redis)</div></div>
        <div className="card kpi-hot"><div className="kpi-value">{data.database.counts.normalized_events ?? 0}</div><div className="kpi-label">Eventos armazenados</div></div>
        <div className="card kpi-hot"><div className="kpi-value">{queues.length}</div><div className="kpi-label">Filas com backlog</div></div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1.4fr 1fr', marginTop: 16 }}>
        <Card title="Maiores tabelas" className="table-wrap">
          <table>
            <thead><tr><th>Tabela</th><th>Tamanho</th><th>Linhas</th></tr></thead>
            <tbody>
              {data.database.top_tables.map((t) => (
                <tr key={t.table}>
                  <td className="mono">{t.table}</td>
                  <td>{t.size_human}</td>
                  <td className="muted">{t.rows.toLocaleString('pt-BR')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <Card title="Filas Celery">
          {queues.length === 0 && <div className="muted">Nenhum backlog. Filas vazias.</div>}
          {queues.map(([q, n]) => (
            <div key={q} className="row" style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
              <span className="mono">{q}</span><span className="spacer" />
              <Badge kind={(n as number) > 1000 ? 'high' : 'info'}>{n}</Badge>
            </div>
          ))}
          <div className="section-title" style={{ marginTop: 16 }}>Configuração</div>
          {Object.entries(data.config).map(([k, v]) => (
            <div key={k} className="row" style={{ fontSize: 12, padding: '3px 0' }}>
              <span className="muted">{k}</span><span className="spacer" /><span className="mono">{String(v)}</span>
            </div>
          ))}
        </Card>
      </div>

      {data.database.unused_indexes.length > 0 && (
        <Card title={`Índices sem uso (${data.database.unused_indexes.length}) — candidatos a revisão`}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
            Índices com 0 varreduras desde o último reset de estatísticas. Podem ser recém-criados (aguardando carga) ou realmente ociosos.
          </div>
          <div className="chips">
            {data.database.unused_indexes.map((i) => <span key={i.index} className="mono muted" style={{ fontSize: 11 }}>{i.index}</span>)}
          </div>
        </Card>
      )}
    </>
  )
}
