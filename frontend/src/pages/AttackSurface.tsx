import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { fmtDate } from '@/lib/format'
import { Badge, Card, Loading } from '@/components/ui'
import type { DetectionResult } from '@/types'

const TABS = [
  { key: 'kerberoasting', label: 'Kerberoasting', path: 'kerberoasting' },
  { key: 'asrep', label: 'AS-REP Roasting', path: 'asrep-roasting' },
  { key: 'stale', label: 'Stale Admins', path: 'stale-admins' },
]

function riskKind(r: number): string {
  if (r >= 80) return 'critical'
  if (r >= 60) return 'high'
  if (r >= 40) return 'medium'
  return 'low'
}

function exportCsv(name: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return
  const cols = ['sam_account_name', 'display_name', 'risk_score', 'is_privileged', 'password_never_expires', 'pwd_last_set', 'reasons']
  const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const csv = [cols.join(',')]
    .concat(rows.map((r) => cols.map((c) => esc(Array.isArray(r[c]) ? (r[c] as string[]).join('; ') : r[c])).join(',')))
    .join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
  const a = document.createElement('a')
  a.href = url; a.download = `${name}.csv`; a.click()
  URL.revokeObjectURL(url)
}

export function AttackSurface() {
  const [tab, setTab] = useState(TABS[0])
  const { data, isLoading } = useQuery({
    queryKey: ['detection', tab.key],
    queryFn: () => api.get<DetectionResult>(`/detections/${tab.path}`),
  })

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Superfície de Ataque</div>
          <div className="page-sub">Detecções defensivas sobre os objetos do AD · MITRE ATT&CK</div>
        </div>
      </div>

      <div className="row" style={{ marginBottom: 14 }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t)} className={tab.key === t.key ? 'primary' : ''}>
            {t.label}
          </button>
        ))}
        <span className="spacer" />
        {data && data.items.length > 0 && (
          <button onClick={() => exportCsv(tab.path, data.items as unknown as Record<string, unknown>[])}>⬇ Exportar CSV</button>
        )}
      </div>

      {isLoading && <Loading />}
      {data && (
        <>
          <div className="card" style={{ marginBottom: 14 }}>
            <div className="row">
              <Badge kind="priv">{data.technique}</Badge>
              <span className="spacer" />
              <span className="mono">{data.count} conta(s)</span>
            </div>
            <div className="muted" style={{ fontSize: 13, marginTop: 8 }}>
              <strong>Recomendação:</strong> {data.recommendation}
            </div>
          </div>

          <Card className="table-wrap">
            <table>
              <thead>
                <tr><th>Conta</th><th>Risco</th><th>Motivos</th><th>Últ. troca senha</th><th>SPN</th></tr>
              </thead>
              <tbody>
                {data.items.map((i) => (
                  <tr key={i.sam_account_name}>
                    <td>
                      <Link to={`/users/${encodeURIComponent(i.sam_account_name)}`} className="mono">{i.sam_account_name}</Link>
                      {i.is_privileged && <Badge kind="priv">priv</Badge>}
                    </td>
                    <td><Badge kind={riskKind(i.risk_score)}>{i.risk_score}</Badge></td>
                    <td>
                      <div className="chips">
                        {i.reasons.map((r) => <span key={r} className="muted" style={{ fontSize: 11 }}>• {r}</span>)}
                      </div>
                    </td>
                    <td className="mono muted">{fmtDate(i.pwd_last_set)}</td>
                    <td className="mono muted" style={{ fontSize: 11 }}>{i.spn?.slice(0, 2).join(', ') || '—'}</td>
                  </tr>
                ))}
                {!data.items.length && <tr><td colSpan={5} className="muted">Nenhuma conta nesta categoria. 🎉</td></tr>}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </>
  )
}
