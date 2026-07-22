import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { api } from '@/lib/api'
import { Badge, Card, Loading } from '@/components/ui'
import { ScoreGauge } from '@/components/widgets'
import type { ADUser, SecurityScore } from '@/types'

interface Category { key: string; label: string; count: number; severity: string }
interface Summary { total_accounts: number; categories: Category[] }

const SEV_COLOR: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e', info: '#38bdf8',
}

export function SecurityPosture() {
  const [active, setActive] = useState<Category | null>(null)
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
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={pie} dataKey="count" nameKey="label" cx="50%" cy="50%" outerRadius={90} innerRadius={45}>
                {pie.map((c) => <Cell key={c.key} fill={SEV_COLOR[c.severity]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
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
