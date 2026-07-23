import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { relative } from '@/lib/format'
import { Card, Loading } from '@/components/ui'
import { BAND } from '@/pages/Findings'

interface Overview {
  total_open: number; suppressed: number
  by_severity: Record<string, number>; by_category: Record<string, number>
  by_asset_type: Record<string, number>; by_environment: Record<string, number>
  fix_first: {
    id: number; title: string; severity: string; risk_score: number; risk_band: string
    category: string; asset_name: string; environment: string; cve?: string; source_tool: string; last_seen: string
  }[]
}
interface Ingestion {
  ingestion_id: string; source_tool: string; total: number; created: number; updated: number
  environment: string; created_by?: string; created_at: string
}

const SEV_ORDER = ['critical', 'high', 'medium', 'low', 'info', 'unknown']
const SEV_COLOR: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e', info: '#38bdf8', unknown: '#8a8a8a',
}

function Bars({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
  const max = Math.max(1, ...entries.map((e) => e[1]))
  return (
    <div>
      {entries.map(([k, v]) => (
        <div key={k} style={{ marginBottom: 8 }}>
          <div className="row" style={{ fontSize: 12, marginBottom: 3 }}><span>{k}</span><span className="spacer" /><span className="mono muted">{v}</span></div>
          <div className="riskbar-track"><div className="riskbar-fill" style={{ width: `${(v / max) * 100}%`, background: SEV_COLOR[k] || 'var(--accent)' }} /></div>
        </div>
      ))}
      {!entries.length && <div className="muted">Sem dados.</div>}
    </div>
  )
}

export function SecurityOverview() {
  const ov = useQuery({ queryKey: ['findings-overview'], queryFn: () => api.get<Overview>('/security/findings/overview'), refetchInterval: 30000 })
  const ing = useQuery({ queryKey: ['findings-ingestions'], queryFn: () => api.get<{ items: Ingestion[] }>('/security/findings/ingestions') })

  if (ov.isLoading || !ov.data) return <Loading />
  const d = ov.data

  return (
    <>
      <div className="hero">
        <div className="hero-scan" />
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Security <span className="accent-text">Operations</span></h1>
            <div className="page-sub" style={{ marginTop: 4 }}>Postura de segurança consolidada · vulnerabilidades, segredos, misconfig e hardening</div>
          </div>
          <span className="live-dot">Ao vivo</span>
        </div>
      </div>

      <div className="grid kpi-row">
        <div className="card kpi-hot"><div className={`kpi-value ${d.by_severity.critical ? 'critical' : ''}`}>{d.by_severity.critical || 0}</div><div className="kpi-label">Críticos abertos</div></div>
        <div className="card kpi-hot"><div className={`kpi-value ${d.by_severity.high ? 'high' : ''}`}>{d.by_severity.high || 0}</div><div className="kpi-label">Altos abertos</div></div>
        <div className="card kpi-hot"><div className="kpi-value">{d.total_open}</div><div className="kpi-label">Total aberto</div></div>
        <div className="card kpi-hot"><div className="kpi-value">{d.by_category.secret || 0}</div><div className="kpi-label">Segredos expostos</div></div>
        <div className="card kpi-hot"><div className="kpi-value">{d.by_category.misconfiguration || 0}</div><div className="kpi-label">Misconfigurações</div></div>
        <div className="card kpi-hot"><div className="kpi-value">{d.suppressed}</div><div className="kpi-label">Suprimidos</div></div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', marginTop: 16 }}>
        <Card title="Por severidade">
          <Bars data={Object.fromEntries(SEV_ORDER.filter((s) => d.by_severity[s]).map((s) => [s, d.by_severity[s]]))} />
        </Card>
        <Card title="Por categoria"><Bars data={d.by_category} /></Card>
        <Card title="Por tipo de ativo"><Bars data={d.by_asset_type} /></Card>
      </div>

      <Card title="Corrigir primeiro — maior risco" className="table-wrap">
        <table>
          <thead><tr><th>Risco</th><th>Título</th><th>Ativo</th><th>Categoria</th><th>CVE</th><th>Fonte</th><th>Visto</th><th></th></tr></thead>
          <tbody>
            {d.fix_first.map((f) => (
              <tr key={f.id}>
                <td><span style={{ fontWeight: 800, color: BAND[f.risk_band] }}>{f.risk_score}</span></td>
                <td>{f.title}</td>
                <td className="mono" style={{ fontSize: 12 }}>{f.asset_name}<div className="muted" style={{ fontSize: 10 }}>{f.environment}</div></td>
                <td className="muted">{f.category}</td>
                <td className="mono muted" style={{ fontSize: 11 }}>{f.cve || '—'}</td>
                <td className="muted">{f.source_tool}</td>
                <td className="mono muted" style={{ fontSize: 11 }}>{relative(f.last_seen)}</td>
                <td><Link to="/security/findings" style={{ fontSize: 12 }}>abrir →</Link></td>
              </tr>
            ))}
            {!d.fix_first.length && <tr><td colSpan={8} className="muted">Nenhum achado ainda. Ingira um scan em “Achados”.</td></tr>}
          </tbody>
        </table>
      </Card>

      {ing.data && !!ing.data.items.length && (
        <Card title="Histórico de ingestões" className="table-wrap">
          <table>
            <thead><tr><th>Quando</th><th>Fonte</th><th>Ambiente</th><th>Total</th><th>Novos</th><th>Atualizados</th><th>Por</th></tr></thead>
            <tbody>
              {ing.data.items.slice(0, 12).map((i) => (
                <tr key={i.ingestion_id}>
                  <td className="mono muted" style={{ fontSize: 11 }}>{relative(i.created_at)}</td>
                  <td>{i.source_tool}</td>
                  <td className="muted">{i.environment}</td>
                  <td>{i.total}</td>
                  <td>{i.created}</td>
                  <td className="muted">{i.updated}</td>
                  <td className="mono muted" style={{ fontSize: 11 }}>{i.created_by || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
