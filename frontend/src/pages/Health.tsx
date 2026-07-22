import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import { api } from '@/lib/api'
import { fmtDate } from '@/lib/format'
import { Card, Loading } from '@/components/ui'
import { Icon } from '@/components/icons'
import { useAuth } from '@/hooks/useAuth'
import type { HealthStatus } from '@/types'

const STATUS: Record<string, { label: string; color: string; bg: string; desc: string }> = {
  HEALTH_OK: { label: 'HEALTH_OK', color: 'var(--low)', bg: 'rgba(55,214,122,0.12)', desc: 'Ambiente saudável — nenhum problema detectado.' },
  HEALTH_WARN: { label: 'HEALTH_WARN', color: 'var(--medium)', bg: 'rgba(255,176,32,0.12)', desc: 'Atenção — há avisos que merecem revisão.' },
  HEALTH_ERR: { label: 'HEALTH_ERR', color: 'var(--critical)', bg: 'rgba(255,45,67,0.14)', desc: 'Crítico — há problemas que exigem ação imediata.' },
}

const SEV_ICON: Record<string, string> = { error: 'alert', warning: 'bell', ok: 'check' }
const SEV_COLOR: Record<string, string> = {
  error: 'var(--critical)', warning: 'var(--medium)', ok: 'var(--low)',
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
  const donut = [
    { k: 'error', label: 'Erros', value: data.summary.error, color: 'var(--critical)' },
    { k: 'warning', label: 'Avisos', value: data.summary.warning, color: 'var(--medium)' },
    { k: 'muted', label: 'Silenciados', value: data.summary.muted, color: 'var(--text-2)' },
  ].filter((d) => d.value > 0)

  return (
    <>
      {/* HERO */}
      <div className="hero">
        <div className="hero-scan" />
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Saúde do <span className="accent-text">Ambiente</span></h1>
            <div className="page-sub" style={{ marginTop: 4 }}>
              Health checks contínuos estilo Ceph · avaliado {fmtDate(data.evaluated_at)}
            </div>
          </div>
          <span className="live-dot">Ao vivo</span>
        </div>
      </div>

      {/* Banner de status + distribuição */}
      <div className="grid" style={{ gridTemplateColumns: '1fr 260px' }}>
        <div className="card" style={{ borderColor: st.color, background: st.bg }}>
          <div className="row" style={{ gap: 18, height: '100%' }}>
            <div style={{
              width: 16, height: 16, borderRadius: '50%', background: st.color,
              boxShadow: `0 0 18px ${st.color}`,
            }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: st.color, letterSpacing: 1 }}>{st.label}</div>
              <div className="muted">{st.desc}</div>
            </div>
            <div className="row" style={{ gap: 22 }}>
              <Stat n={data.summary.error} label="erros" color="var(--critical)" />
              <Stat n={data.summary.warning} label="avisos" color="var(--medium)" />
              <Stat n={data.summary.muted} label="silenciados" color="var(--text-2)" />
            </div>
          </div>
        </div>

        <Card title="Distribuição">
          {donut.length > 0 ? (
            <ResponsiveContainer width="100%" height={150}>
              <PieChart>
                <Pie data={donut} dataKey="value" nameKey="label" cx="50%" cy="50%" innerRadius={42} outerRadius={62} paddingAngle={2}>
                  {donut.map((d) => <Cell key={d.k} fill={d.color} />)}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          ) : <div className="muted" style={{ padding: 20 }}>Sem checks ativos.</div>}
          <div className="row" style={{ justifyContent: 'center', gap: 14, fontSize: 11, marginTop: -6 }}>
            {donut.map((d) => (
              <span key={d.k} className="row" style={{ gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: d.color, display: 'inline-block' }} />
                {d.label}
              </span>
            ))}
          </div>
        </Card>
      </div>

      {/* Lista de checks */}
      <div style={{ marginTop: 16 }}>
      <Card title={`Health checks (${data.checks.length})`}>
        {!data.checks.length && (
          <div className="row" style={{ gap: 8, color: 'var(--low)', padding: '8px 0' }}>
            <Icon name="check" size={18} /> Nenhum check ativo. Ambiente 100% saudável.
          </div>
        )}
        {data.checks.map((c) => (
          <div key={c.id} style={{
            display: 'flex', gap: 12, padding: '12px 0', borderBottom: '1px solid var(--border)',
            opacity: c.muted ? 0.5 : 1,
          }}>
            <div style={{ width: 3, borderRadius: 3, background: SEV_COLOR[c.severity] || 'var(--border)' }} />
            <div style={{ color: SEV_COLOR[c.severity], paddingTop: 2 }}>
              <Icon name={SEV_ICON[c.severity] || 'dot'} size={18} />
            </div>
            <div style={{ flex: 1 }}>
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
          </div>
        ))}
      </Card>
      </div>

      <div className="muted" style={{ fontSize: 11, marginTop: 12 }}>
        Estes health checks alimentam o sino de notificações e os alertas automáticos
        para o Google Chat (webhook), quando configurados.
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
