import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Badge, Card, Loading } from '@/components/ui'
import { Icon } from '@/components/icons'
import { fmtDate, fmtBytes, eventLabel } from '@/lib/format'
import { useAuth } from '@/hooks/useAuth'

interface CapacityData {
  database: {
    size_human: string
    counts: Record<string, number | null>
    top_tables: { table: string; size_human: string; rows: number }[]
    unused_indexes: { table: string; index: string }[]
  }
  redis: Record<string, string | number>
  celery_queues: Record<string, number | null>
  ingestion: {
    events_1h: number
    events_24h: number
    events_7d: number
    by_type: { type: string; count: number }[]
  }
  config: Record<string, unknown>
}

interface MaintStatus {
  database_bytes: number
  tables: { table: string; bytes: number; rows: number; dead_rows: number }[]
  policies: { data_type: string; retention_days: number; last_purge_at?: string }[]
  config: Record<string, unknown>
}

export function Capacity() {
  const qc = useQueryClient()
  const { can } = useAuth()
  const isAdmin = can('*')
  const [cleanMsg, setCleanMsg] = useState('')
  const [rawDays, setRawDays] = useState<string>('')
  const { data, isLoading } = useQuery({
    queryKey: ['capacity'],
    queryFn: () => api.get<CapacityData>('/admin/capacity'),
    refetchInterval: 30000,
  })
  const maint = useQuery({
    queryKey: ['maint-status'],
    queryFn: () => api.get<MaintStatus>('/admin/maintenance/status'),
    refetchInterval: 30000,
  })
  const cleanup = useMutation({
    mutationFn: (opts: { full?: boolean; raw_days?: number }) => {
      const p = new URLSearchParams()
      if (opts.full) p.set('full', 'true')
      if (opts.raw_days != null) p.set('raw_days', String(opts.raw_days))
      const qs = p.toString()
      return api.post<{ stats: Record<string, number | string> }>(`/admin/maintenance/cleanup${qs ? '?' + qs : ''}`)
    },
    onSuccess: (r) => {
      const s = r.stats || {}
      const n = (k: string) => Number(s[k] ?? 0)
      let msg = `Limpeza concluída — JSON bruto limpo: ${n('raw_json_cleared')}, eventos: ${n('events_deleted')}, auditoria: ${n('audit_deleted')}, notificações: ${n('notifications_deleted')}.`
      if (n('vacuum')) msg += ` Espaço recuperado: ${fmtBytes(n('bytes_reclaimed'))}${n('vacuum_full') ? ' (VACUUM FULL)' : ''}.`
      else if (s.vacuum_error) msg += ` VACUUM falhou: ${s.vacuum_error}`
      setCleanMsg(msg)
      qc.invalidateQueries({ queryKey: ['maint-status'] })
      qc.invalidateQueries({ queryKey: ['capacity'] })
    },
    onError: (e) => setCleanMsg('Falha: ' + (e as Error).message),
  })
  const runCleanup = (full: boolean) => {
    if (full && !window.confirm('VACUUM FULL reescreve as tabelas grandes e aplica um lock exclusivo breve (a aplicação pode ficar lenta por alguns segundos). Recupera espaço em disco de fato. Continuar?')) return
    setCleanMsg('')
    const rd = rawDays.trim() === '' ? undefined : Math.max(0, parseInt(rawDays, 10))
    cleanup.mutate({ full, raw_days: rd })
  }

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

      {/* Ingestão de eventos — taxa e distribuição */}
      <Card title="Ingestão de Eventos — taxa e distribuição (24h)">
        <div className="grid kpi-row" style={{ marginBottom: 14 }}>
          <div className="card kpi-hot"><div className="kpi-value">{data.ingestion.events_1h.toLocaleString('pt-BR')}</div><div className="kpi-label">Última hora</div></div>
          <div className="card kpi-hot"><div className="kpi-value">{data.ingestion.events_24h.toLocaleString('pt-BR')}</div><div className="kpi-label">Últimas 24h</div></div>
          <div className="card kpi-hot"><div className="kpi-value">{Math.round(data.ingestion.events_24h / 24).toLocaleString('pt-BR')}</div><div className="kpi-label">Média por hora (24h)</div></div>
          <div className="card kpi-hot"><div className="kpi-value">{data.ingestion.events_7d.toLocaleString('pt-BR')}</div><div className="kpi-label">Últimos 7 dias</div></div>
        </div>
        {data.ingestion.by_type.length === 0 && <div className="muted">Nenhum evento ingerido nas últimas 24h.</div>}
        {data.ingestion.by_type.length > 0 && (() => {
          const max = Math.max(...data.ingestion.by_type.map((x) => x.count), 1)
          return (
            <>
              <div className="section-title" style={{ marginTop: 0 }}>Distribuição por tipo (24h)</div>
              {data.ingestion.by_type.map((t) => (
                <div key={t.type} style={{ marginBottom: 8 }}>
                  <div className="row" style={{ marginBottom: 3, fontSize: 12 }}>
                    <span>{eventLabel(t.type)}</span>
                    <span className="spacer" />
                    <span className="mono muted">{t.count.toLocaleString('pt-BR')}</span>
                  </div>
                  <div className="riskbar-track"><div className="riskbar-fill" style={{ width: `${(t.count / max) * 100}%` }} /></div>
                </div>
              ))}
            </>
          )
        })()}
      </Card>

      {/* Manutenção do banco */}
      <Card title="Manutenção do Banco">
        <div className="row" style={{ marginBottom: 12, alignItems: 'flex-start' }}>
          <div style={{ flex: 1 }}>
            <div className="muted" style={{ fontSize: 13 }}>
              Limpeza por retenção (purge em lotes) + recuperação de espaço. O maior consumo vem do
              JSON bruto dos eventos — reduza o horizonte abaixo para liberar volume, e use
              <b> VACUUM FULL</b> para encolher o arquivo em disco de fato.
            </div>
            {maint.data && (
              <div className="row" style={{ gap: 18, marginTop: 8, fontSize: 12 }}>
                <span className="muted">Banco: <b className="mono">{fmtBytes(maint.data.database_bytes)}</b></span>
                <span className="muted">Retenção JSON bruto atual: <b className="mono">{String(maint.data.config.raw_retention_days)}d</b></span>
              </div>
            )}
          </div>
        </div>
        {isAdmin && (
          <div className="row" style={{ gap: 10, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            <label className="muted" style={{ fontSize: 12 }}>Limpar JSON bruto de eventos com mais de</label>
            <input
              type="number" min={0} value={rawDays} onChange={(e) => setRawDays(e.target.value)}
              placeholder={String(maint.data?.config.raw_retention_days ?? '')}
              style={{ width: 70, textAlign: 'center' }}
            />
            <span className="muted" style={{ fontSize: 12 }}>dias (vazio = política padrão)</span>
            <span className="spacer" />
            <button className="btn-icon" disabled={cleanup.isPending} onClick={() => runCleanup(false)}>
              <Icon name="trash" size={15} /> {cleanup.isPending ? 'Executando…' : 'Executar limpeza'}
            </button>
            <button className="primary btn-icon" disabled={cleanup.isPending} onClick={() => runCleanup(true)}>
              <Icon name="zap" size={15} /> Recuperar espaço (VACUUM FULL)
            </button>
          </div>
        )}
        {cleanMsg && <div className="muted" style={{ fontSize: 12, marginBottom: 10, color: cleanMsg.startsWith('Falha') || cleanMsg.includes('falhou') ? 'var(--critical)' : 'var(--low)' }}>{cleanMsg}</div>}
        {maint.data && (
          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <div className="table-wrap">
              <div className="section-title" style={{ marginTop: 0 }}>Retenção configurada</div>
              <table>
                <thead><tr><th>Tipo</th><th>Dias</th><th>Última limpeza</th></tr></thead>
                <tbody>
                  {maint.data.policies.map((p) => (
                    <tr key={p.data_type}>
                      <td>{p.data_type}</td>
                      <td>{p.retention_days}</td>
                      <td className="mono muted">{fmtDate(p.last_purge_at)}</td>
                    </tr>
                  ))}
                  {!maint.data.policies.length && <tr><td colSpan={3} className="muted">Nenhuma limpeza executada ainda.</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="table-wrap">
              <div className="section-title" style={{ marginTop: 0 }}>Linhas mortas (bloat) por tabela</div>
              <table>
                <thead><tr><th>Tabela</th><th>Linhas</th><th>Mortas</th></tr></thead>
                <tbody>
                  {maint.data.tables.filter((t) => t.dead_rows > 0).slice(0, 8).map((t) => (
                    <tr key={t.table}>
                      <td className="mono">{t.table}</td>
                      <td>{t.rows.toLocaleString('pt-BR')}</td>
                      <td><Badge kind={t.dead_rows > 10000 ? 'high' : 'medium'}>{t.dead_rows.toLocaleString('pt-BR')}</Badge></td>
                    </tr>
                  ))}
                  {!maint.data.tables.some((t) => t.dead_rows > 0) && <tr><td colSpan={3} className="muted">Sem bloat relevante.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Card>

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
