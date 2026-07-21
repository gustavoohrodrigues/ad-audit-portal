import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { api } from '@/lib/api'
import { Badge, Card, Loading } from '@/components/ui'
import type { ADUser } from '@/types'

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
  const accounts = useQuery({
    queryKey: ['inv-accounts', active?.key],
    queryFn: () => api.get<{ label: string; count: number; items: ADUser[] }>(`/inventory/accounts?category=${active!.key}`),
    enabled: !!active,
  })

  if (summary.isLoading || !summary.data) return <Loading />
  const d = summary.data
  const pie = d.categories.filter((c) => c.count > 0 && !['disabled'].includes(c.key)).slice(0, 8)

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Postura de Segurança</div>
          <div className="page-sub">{d.total_accounts} contas sincronizadas · clique numa categoria para investigar</div>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 320px' }}>
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
