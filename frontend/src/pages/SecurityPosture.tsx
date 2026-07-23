import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { PieChart, Pie, Cell, ResponsiveContainer, Sector } from 'recharts'
import { api } from '@/lib/api'
import { Badge, Card, Loading } from '@/components/ui'
import { ScoreGauge } from '@/components/widgets'
import { Icon } from '@/components/icons'
import { exportReport, REPORT_SEV } from '@/lib/dashboardReport'
import type { ADUser, SecurityScore } from '@/types'

interface Category { key: string; label: string; count: number; severity: string }
interface Summary { total_accounts: number; categories: Category[] }

const SEV_COLOR: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e', info: '#38bdf8',
}

// Fatia destacada (hover/seleção): expande, arredonda e ganha brilho.
function renderActiveShape(props: any) {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill } = props
  return (
    <g>
      <Sector cx={cx} cy={cy} innerRadius={innerRadius} outerRadius={outerRadius + 9}
        startAngle={startAngle} endAngle={endAngle} fill={fill} cornerRadius={6}
        style={{ filter: `drop-shadow(0 0 10px ${fill})` }} />
      <Sector cx={cx} cy={cy} innerRadius={outerRadius + 12} outerRadius={outerRadius + 14}
        startAngle={startAngle} endAngle={endAngle} fill={fill} opacity={0.45} />
    </g>
  )
}

export function SecurityPosture() {
  const [active, setActive] = useState<Category | null>(null)
  const [hover, setHover] = useState<number | null>(null)
  const summary = useQuery({
    queryKey: ['inv-summary'],
    queryFn: () => api.get<Summary>('/inventory/summary'),
    refetchInterval: 60000,
  })
  const score = useQuery({
    queryKey: ['sec-score-posture'],
    queryFn: () => api.get<SecurityScore>('/dashboard/security-score'),
    refetchInterval: 60000,
  })
  const accounts = useQuery({
    queryKey: ['inv-accounts', active?.key],
    queryFn: () => api.get<{ label: string; count: number; items: ADUser[] }>(`/inventory/accounts?category=${active!.key}`),
    enabled: !!active,
  })

  if (summary.isLoading || !summary.data) return <Loading />
  const d = summary.data
  const pie = d.categories.filter((c) => c.count > 0 && !['disabled'].includes(c.key)).slice(0, 8)
  const maxImpact = Math.max(1, ...(score.data?.factors || []).map((f) => f.impact))
  const totalFlagged = pie.reduce((s, c) => s + c.count, 0)
  const shown = hover != null ? pie[hover] : null
  const pct = (n: number) => (totalFlagged ? Math.round((n / totalFlagged) * 100) : 0)

  return (
    <>
      {/* HERO */}
      <div className="hero">
        <div className="hero-scan" />
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Postura de <span className="accent-text">Segurança</span></h1>
            <div className="page-sub" style={{ marginTop: 4 }}>
              {d.total_accounts} contas sincronizadas · clique numa categoria para investigar
            </div>
          </div>
          <button className="btn-icon" onClick={() => exportReport({
            title: 'Relatório de Postura de Segurança',
            subtitle: `${d.total_accounts} contas sincronizadas`,
            score: score.data ? { score: score.data.score, grade: score.data.grade } : undefined,
            categories: d.categories.filter((c) => c.count > 0 && c.key !== 'disabled').map((c) => ({ label: c.label, value: c.count, color: REPORT_SEV[c.severity] || '#38bdf8' })),
            factors: score.data?.factors,
          })}>
            <Icon name="download" size={14} /> Exportar PDF
          </button>
        </div>
      </div>

      {/* Score + fatores */}
      <div className="grid" style={{ gridTemplateColumns: '300px 1fr' }}>
        <Card title="Security Score">
          {score.data ? <ScoreGauge score={score.data.score} grade={score.data.grade} /> : <Loading />}
        </Card>
        <Card title="Fatores que pesam na nota">
          {!score.data && <Loading />}
          {score.data && score.data.factors.map((f) => (
            <div key={f.label} style={{ marginBottom: 10 }}>
              <div className="row" style={{ marginBottom: 3, fontSize: 12 }}>
                <Badge kind={f.severity}>{f.severity}</Badge>
                <span style={{ flex: 1 }}>{f.label}</span>
                <span className="mono muted">{f.count}</span>
                <span className="mono" style={{ marginLeft: 10, color: SEV_COLOR[f.severity] }}>-{f.impact}</span>
              </div>
              <div className="riskbar-track">
                <div className="riskbar-fill" style={{ width: `${(f.impact / maxImpact) * 100}%`, background: SEV_COLOR[f.severity] }} />
              </div>
            </div>
          ))}
          {score.data && !score.data.factors.length && (
            <div className="muted">Nenhum fator de risco relevante. Excelente postura.</div>
          )}
        </Card>
      </div>

      {/* Categorias + distribuição */}
      <div className="grid" style={{ gridTemplateColumns: '1fr 320px', marginTop: 16 }}>
        <div className="grid kpi-row">
          {d.categories.map((c) => (
            <button
              key={c.key}
              onClick={() => setActive(c)}
              className="card"
              style={{
                textAlign: 'left', cursor: 'pointer',
                borderColor: active?.key === c.key ? SEV_COLOR[c.severity] : undefined,
              }}
            >
              <div className={`kpi-value ${c.severity}`}>{c.count}</div>
              <div className="kpi-label">{c.label}</div>
              <div style={{ marginTop: 6 }}><Badge kind={c.severity}>{c.severity}</Badge></div>
            </button>
          ))}
        </div>

        <Card title="Distribuição de risco">
          <div style={{ position: 'relative' }}>
            <ResponsiveContainer width="100%" height={230}>
              <PieChart>
                <defs>
                  {pie.map((c, i) => (
                    <linearGradient key={c.key} id={`pg${i}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={SEV_COLOR[c.severity]} stopOpacity={0.98} />
                      <stop offset="100%" stopColor={SEV_COLOR[c.severity]} stopOpacity={0.5} />
                    </linearGradient>
                  ))}
                </defs>
                <Pie
                  data={pie} dataKey="count" nameKey="label" cx="50%" cy="50%"
                  innerRadius={66} outerRadius={92} paddingAngle={3} cornerRadius={5}
                  stroke="none" startAngle={90} endAngle={-270}
                  activeIndex={hover ?? undefined} activeShape={renderActiveShape}
                  onMouseEnter={(_, i) => setHover(i)}
                  onMouseLeave={() => setHover(null)}
                  onClick={(_, i) => setActive(pie[i])}
                >
                  {pie.map((c, i) => <Cell key={c.key} fill={`url(#pg${i})`} cursor="pointer" />)}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            {/* Rótulo central */}
            <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', pointerEvents: 'none' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 32, fontWeight: 800, lineHeight: 1, color: shown ? SEV_COLOR[shown.severity] : 'var(--text-0)' }}>
                  {shown ? shown.count : totalFlagged}
                </div>
                <div className="muted" style={{ fontSize: 11, marginTop: 4, maxWidth: 130 }}>
                  {shown ? shown.label : 'contas sinalizadas'}
                </div>
                {shown && <div className="mono" style={{ fontSize: 11, marginTop: 2, color: SEV_COLOR[shown.severity] }}>{pct(shown.count)}%</div>}
              </div>
            </div>
          </div>
          {/* Legenda interativa */}
          <div style={{ marginTop: 8 }}>
            {pie.map((c, i) => (
              <div
                key={c.key}
                className="row"
                style={{
                  fontSize: 12, padding: '5px 6px', borderRadius: 7, cursor: 'pointer',
                  opacity: hover == null || hover === i ? 1 : 0.45,
                  background: hover === i ? 'var(--bg-3)' : 'transparent', transition: 'opacity .15s, background .15s',
                }}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                onClick={() => setActive(c)}
              >
                <span style={{ width: 10, height: 10, borderRadius: 3, background: SEV_COLOR[c.severity], boxShadow: `0 0 7px ${SEV_COLOR[c.severity]}`, flexShrink: 0 }} />
                <span style={{ flex: 1, marginLeft: 9 }}>{c.label}</span>
                <span className="mono muted">{c.count}</span>
                <span className="mono" style={{ marginLeft: 12, width: 34, textAlign: 'right', color: SEV_COLOR[c.severity] }}>{pct(c.count)}%</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {active && (
        <Card title={`${active.label} — ${accounts.data?.count ?? '…'} conta(s)`} className="table-wrap">
          <button onClick={() => setActive(null)} style={{ float: 'right' }}>Fechar</button>
          {accounts.isLoading && <Loading />}
          {accounts.data && (
            <table>
              <thead><tr><th>Login</th><th>Nome</th><th>Departamento</th><th>Últ. logon</th><th>Flags</th></tr></thead>
              <tbody>
                {accounts.data.items.map((u) => (
                  <tr key={u.sam_account_name}>
                    <td><Link to={`/users/${encodeURIComponent(u.sam_account_name)}`} className="mono">{u.sam_account_name}</Link></td>
                    <td>{u.display_name || '—'}</td>
                    <td>{u.department || '—'}</td>
                    <td className="mono muted">{u.last_logon_timestamp?.slice(0, 10) || '—'}</td>
                    <td>
                      <div className="chips">
                        {u.is_privileged && <Badge kind="priv">priv</Badge>}
                        {u.is_critical && <Badge kind="crit-acct">crítico</Badge>}
                        {u.password_never_expires && <Badge kind="medium">senha ∞</Badge>}
                        {u.is_disabled && <Badge kind="low">desab.</Badge>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </>
  )
}
