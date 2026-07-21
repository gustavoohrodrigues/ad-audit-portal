import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { fmtDate } from '@/lib/format'
import { Card, Loading } from '@/components/ui'
import { useAuth } from '@/hooks/useAuth'
import type { HealthStatus } from '@/types'

const STATUS: Record<string, { label: string; color: string; bg: string; desc: string }> = {
  HEALTH_OK: { label: 'HEALTH_OK', color: 'var(--low)', bg: 'rgba(55,214,122,0.12)', desc: 'Ambiente saudável — nenhum problema detectado.' },
  HEALTH_WARN: { label: 'HEALTH_WARN', color: 'var(--medium)', bg: 'rgba(255,176,32,0.12)', desc: 'Atenção — há avisos que merecem revisão.' },
  HEALTH_ERR: { label: 'HEALTH_ERR', color: 'var(--critical)', bg: 'rgba(255,45,67,0.14)', desc: 'Crítico — há problemas que exigem ação imediata.' },
}

export function Health() {
  const qc = useQueryClient()
  const { can } = useAuth()
  const isAdmin = can('*') || can('investigation:manage')
  const { data, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<HealthStatus>('/monitoring/health'),
    refetchInterval: 20000,
  })
  const mute = useMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) =>
      api.post(`/monitoring/checks/${id}/${on ? 'mute' : 'unmute'}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['health'] }),
  })

  if (isLoading || !data) return <Loading />
  const st = STATUS[data.status]

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Saúde do Ambiente</div>
          <div className="page-sub">Health checks contínuos · avaliado {fmtDate(data.evaluated_at)}</div>
        </div>
      </div>

      {/* Banner de status estilo Ceph */}
      <div className="card" style={{ borderColor: st.color, background: st.bg, marginBottom: 16 }}>
        <div className="row" style={{ gap: 18 }}>
          <div style={{
            width: 14, height: 14, borderRadius: '50%', background: st.color,
            boxShadow: `0 0 16px ${st.color}`,
          }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 24, fontWeight: 800, color: st.color, letterSpacing: 1 }}>{st.label}</div>
            <div className="muted">{st.desc}</div>
          </div>
          <div className="row" style={{ gap: 20 }}>
            <Stat n={data.summary.error} label="erros" color="var(--critical)" />
            <Stat n={data.summary.warning} label="avisos" color="var(--medium)" />
            <Stat n={data.summary.muted} label="silenciados" color="var(--text-2)" />
          </div>
        </div>
      </div>

      {/* Lista de checks */}
      <Card title={`Health checks (${data.checks.length})`}>
        {!data.checks.length && <div className="muted">Nenhum check ativo. Ambiente 100% saudável.</div>}
        {data.checks.map((c) => (
          <div key={c.id} style={{
            padding: '12px 0', borderBottom: '1px solid var(--border)',
            opacity: c.muted ? 0.5 : 1,
          }}>
            <div className="row">
              <span className={`badge ${c.severity}`}>{c.severity}</span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-2)' }}>{c.id}</span>
              <span className="spacer" />
              {c.link && <Link to={c.link} style={{ fontSize: 12 }}>Investigar →</Link>}
              {isAdmin && (
                <button
                  onClick={() => mute.mutate({ id: c.id, on: !c.muted })}
                  style={{ padding: '3px 10px', fontSize: 11 }}
                >
                  {c.muted ? 'Reativar' : 'Silenciar'}
                </button>
              )}
            </div>
            <div style={{ marginTop: 6, fontWeight: 600 }}>{c.summary}</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{c.detail}</div>
          </div>
        ))}
      </Card>

      <div className="muted" style={{ fontSize: 11, marginTop: 12 }}>
        Estes health checks alimentam o sino de notificações e estão prontos para,
        no futuro, serem enviados a canais de chat (Teams/Slack/Discord) via webhook.
      </div>
    </>
  )
}

function Stat({ n, label, color }: { n: number; label: string; color: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 26, fontWeight: 800, color }}>{n}</div>
      <div className="muted" style={{ fontSize: 11 }}>{label}</div>
    </div>
  )
}
