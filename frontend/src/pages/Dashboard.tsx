import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '@/lib/api'
import { fmtTime } from '@/lib/format'
import { Badge, Card, Loading, StatusDot } from '@/components/ui'
import { AnimatedNumber, ScoreGauge } from '@/components/widgets'
import type {
  DashboardSummary,
  DomainControllerHealth,
  InventoryCategory,
  ScorePoint,
  SecurityScore,
} from '@/types'

function HotKpi({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className="card kpi-hot">
      <div className={`kpi-value ${tone || ''}`}><AnimatedNumber value={value} /></div>
      <div className="kpi-label">{label}</div>
    </div>
  )
}

export function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get<DashboardSummary>('/dashboard/summary'),
    refetchInterval: 30000,
  })
  const dcs = useQuery({
    queryKey: ['dcs'],
    queryFn: () => api.get<{ items: DomainControllerHealth[] }>('/dashboard/domain-controllers'),
    refetchInterval: 30000,
  })
  const score = useQuery({
    queryKey: ['sec-score'],
    queryFn: () => api.get<SecurityScore>('/dashboard/security-score'),
    refetchInterval: 60000,
  })
  const inv = useQuery({
    queryKey: ['inv-sum-dash'],
    queryFn: () => api.get<{ total_accounts: number; categories: InventoryCategory[] }>('/inventory/summary'),
    refetchInterval: 60000,
  })
  const history = useQuery({
    queryKey: ['score-history'],
    queryFn: () => api.get<{ series: ScorePoint[] }>('/dashboard/security-score/history?days=90'),
  })

  if (isLoading || !data) return <Loading />

  const chartData = data.failed_logons_by_hour.map((b) => ({ h: fmtTime(b.ts).slice(0, 5), count: b.count }))
  const now = new Date().toLocaleTimeString('pt-BR')

  return (
    <>
      {/* HERO */}
      <div className="hero">
        <div className="hero-scan" />
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Centro de <span className="accent-text">Operações</span> de Identidade</h1>
            <div className="page-sub" style={{ marginTop: 4 }}>
              Monitoramento contínuo do Active Directory · atualizado {now}
            </div>
          </div>
          <span className="live-dot">Ao vivo</span>
        </div>
      </div>

      {/* SCORE + KPIs quentes */}
      <div className="grid" style={{ gridTemplateColumns: '300px 1fr' }}>
        <Card title="Score de Segurança do AD">
          {score.data ? (
            <>
              <ScoreGauge score={score.data.score} grade={score.data.grade} />
              <div style={{ marginTop: 10 }}>
                {score.data.factors.slice(0, 4).map((f) => (
                  <div key={f.label} className="row" style={{ fontSize: 12, padding: '3px 0' }}>
                    <Badge kind={f.severity}>{f.impact}</Badge>
                    <span className="muted" style={{ flex: 1 }}>{f.label}</span>
                    <span className="mono">{f.count}</span>
                  </div>
                ))}
              </div>
              {history.data && history.data.series.length >= 2 && (
                <div style={{ marginTop: 12 }}>
                  <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>Tendência (90d)</div>
                  <ResponsiveContainer width="100%" height={60}>
                    <LineChart data={history.data.series}>
                      <YAxis domain={[0, 100]} hide />
                      <Tooltip contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-bright)', borderRadius: 8, fontSize: 11 }} labelFormatter={(l) => `Dia ${l}`} />
                      <Line type="monotone" dataKey="score" stroke="#ff2d43" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
              <Link to="/posture" style={{ fontSize: 12, display: 'inline-block', marginTop: 8 }}>
                Ver postura completa →
              </Link>
            </>
          ) : <Loading />}
        </Card>

        <div className="grid kpi-row" style={{ alignContent: 'start' }}>
          <HotKpi label="Bloqueios (24h)" value={data.lockouts_24h} tone={data.lockouts_24h > 10 ? 'critical' : ''} />
          <HotKpi label="Falhas de auth (24h)" value={data.failed_logons_24h} tone={data.failed_logons_24h > 50 ? 'high' : ''} />
          <HotKpi label="Alertas críticos" value={data.critical_alerts_open} tone="critical" />
          <HotKpi label="Contas privilegiadas" value={data.privileged_accounts} tone="high" />
          <HotKpi label="Senha nunca expira" value={data.never_expire_accounts} tone="medium" />
          <HotKpi label="Contas inativas" value={data.inactive_accounts} tone="medium" />
          <HotKpi label="Eventos senha (24h)" value={data.password_events_24h} />
          <HotKpi label="Grupos priv. (24h)" value={data.privileged_group_changes_24h} tone={data.privileged_group_changes_24h > 0 ? 'critical' : ''} />
        </div>
      </div>

      {/* Gráfico + risco */}
      <div className="grid" style={{ gridTemplateColumns: '2fr 1fr', marginTop: 16 }}>
        <Card title="Falhas de autenticação por hora (24h)">
          <ResponsiveContainer width="100%" height={230}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="gRed" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ff2d43" stopOpacity={0.6} />
                  <stop offset="100%" stopColor="#ff2d43" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="h" stroke="var(--text-2)" fontSize={11} />
              <YAxis stroke="var(--text-2)" fontSize={11} allowDecimals={false} />
              <Tooltip contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-bright)', borderRadius: 8 }} />
              <Area type="monotone" dataKey="count" stroke="#ff2d43" fill="url(#gRed)" strokeWidth={2.5} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Exposição de contas">
          {inv.data ? inv.data.categories.filter((c) => c.count > 0).slice(0, 7).map((c) => {
            const max = Math.max(...inv.data!.categories.map((x) => x.count), 1)
            return (
              <div key={c.key} style={{ marginBottom: 9 }}>
                <div className="row" style={{ marginBottom: 3, fontSize: 12 }}>
                  <span>{c.label}</span><span className="spacer" /><span className="mono">{c.count}</span>
                </div>
                <div className="riskbar-track"><div className="riskbar-fill" style={{ width: `${(c.count / max) * 100}%` }} /></div>
              </div>
            )
          }) : <Loading />}
        </Card>
      </div>

      {/* Rankings + DCs */}
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', marginTop: 16 }}>
        <RankCard title="Usuários mais bloqueados" items={data.top_locked_users} linkUser />
        <RankCard title="Computadores de origem" items={data.top_source_computers} />
        <Card title="Domain Controllers">
          {(dcs.data?.items || []).map((dc) => (
            <div className="row" key={dc.hostname} style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
              <StatusDot status={dc.status} />
              <span className="mono">{dc.hostname}</span>
              <span className="spacer" />
              <span className="muted">{dc.event_count_24h} evt</span>
            </div>
          ))}
          {!dcs.data?.items.length && <div className="muted">Sem DCs registrados ainda.</div>}
        </Card>
      </div>
    </>
  )
}

function RankCard({ title, items, linkUser }: { title: string; items: { label: string; count: number }[]; linkUser?: boolean }) {
  const max = Math.max(1, ...items.map((i) => i.count))
  return (
    <Card title={title}>
      {!items.length && <div className="muted">Sem dados no período.</div>}
      {items.map((i) => (
        <div key={i.label} style={{ marginBottom: 8 }}>
          <div className="row" style={{ marginBottom: 3 }}>
            <span className="mono" style={{ fontSize: 12 }}>
              {linkUser ? <Link to={`/users/${encodeURIComponent(i.label)}`}>{i.label}</Link> : i.label}
            </span>
            <span className="spacer" />
            <span className="muted">{i.count}</span>
          </div>
          <div className="riskbar-track"><div className="riskbar-fill" style={{ width: `${(i.count / max) * 100}%` }} /></div>
        </div>
      ))}
    </Card>
  )
}
