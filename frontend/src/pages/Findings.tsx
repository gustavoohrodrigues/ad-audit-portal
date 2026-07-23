import { useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { fmtDate, relative } from '@/lib/format'
import { Badge, Card, Loading } from '@/components/ui'
import { Icon } from '@/components/icons'
import { useAuth } from '@/hooks/useAuth'

interface Finding {
  id: number; title: string; severity: string; risk_score: number; risk_band: string
  category: string; asset_type: string; asset_name: string; environment: string; cve?: string
  package_name?: string; fixed_version?: string; status: string; source_tool: string
  occurrences: number; last_seen: string; first_seen: string
}
interface Detail extends Finding {
  description?: string; evidence?: Record<string, unknown>; remediation?: string; references?: string[]
  cwe?: string; cvss?: number; installed_version?: string; file_path?: string; config_path?: string
  host_name?: string; service_name?: string; exploit_available?: boolean; internet_exposed?: boolean
  privileged_context?: boolean; remediation_state?: string; assignee?: string
  suppressed_until?: string; suppression_reason?: string; suppressed_by?: string; tags?: string[]
}

export const BAND: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e', info: '#38bdf8',
}
const SEV_KIND: Record<string, 'critical' | 'high' | 'medium' | 'low' | 'info'> = {
  critical: 'critical', high: 'high', medium: 'medium', low: 'low', info: 'info', unknown: 'info',
}
const TITLES: Record<string, string> = {
  vulnerability: 'Vulnerabilidades', misconfiguration: 'Misconfigurações', secret: 'Segredos expostos',
  hardening: 'Hardening', image: 'Segurança de Contêineres',
}

export function Findings() {
  const [sp] = useSearchParams()
  const { can } = useAuth()
  const canWrite = can('*') || can('investigation:manage')
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)

  const initCategory = sp.get('category') || ''
  const initAsset = sp.get('asset_type') || ''
  const heading = TITLES[initCategory] || TITLES[initAsset] || 'Todos os Achados'

  const [q, setQ] = useState('')
  const [severity, setSeverity] = useState('')
  const [status, setStatus] = useState('open')
  const [env, setEnv] = useState('')
  const [page, setPage] = useState(1)
  const [openId, setOpenId] = useState<number | null>(null)
  const [ingestEnv, setIngestEnv] = useState('production')
  const [ingestMsg, setIngestMsg] = useState('')
  const [supReason, setSupReason] = useState('')

  const params = useMemo(() => {
    const p = new URLSearchParams()
    p.set('status', status); p.set('page', String(page)); p.set('page_size', '50')
    if (initCategory) p.set('category', initCategory)
    if (initAsset) p.set('asset_type', initAsset)
    if (severity) p.set('severity', severity)
    if (env) p.set('environment', env)
    if (q.trim()) p.set('q', q.trim())
    return p.toString()
  }, [status, page, initCategory, initAsset, severity, env, q])

  const list = useQuery({
    queryKey: ['findings', params],
    queryFn: () => api.get<{ total: number; items: Finding[] }>(`/security/findings?${params}`),
  })
  const detail = useQuery({
    queryKey: ['finding', openId],
    queryFn: () => api.get<Detail>(`/security/findings/${openId}`),
    enabled: openId != null,
  })
  const ingest = useMutation({
    mutationFn: (content: unknown) => api.post('/security/findings/ingest', { format: 'trivy', content, environment: ingestEnv }),
    onSuccess: (r) => { setIngestMsg(`Ingestão concluída: ${(r as { created: number }).created} novos, ${(r as { updated: number }).updated} atualizados.`); qc.invalidateQueries({ queryKey: ['findings'] }) },
    onError: (e) => setIngestMsg('Falha: ' + (e as Error).message),
  })
  const suppress = useMutation({
    mutationFn: (v: { id: number; reason: string; days: number }) => api.post(`/security/findings/${v.id}/suppress`, { reason: v.reason, days: v.days }),
    onSuccess: () => { setSupReason(''); qc.invalidateQueries({ queryKey: ['findings'] }); qc.invalidateQueries({ queryKey: ['finding', openId] }) },
  })
  const setState = useMutation({
    mutationFn: (v: { id: number; state: string }) => api.post(`/security/findings/${v.id}/state`, { remediation_state: v.state }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['findings'] }); qc.invalidateQueries({ queryKey: ['finding', openId] }) },
  })

  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    setIngestMsg('')
    const reader = new FileReader()
    reader.onload = () => {
      try { ingest.mutate(JSON.parse(String(reader.result))) }
      catch { setIngestMsg('Arquivo não é um JSON válido do Trivy.') }
    }
    reader.readAsText(f)
    e.target.value = ''
  }

  return (
    <>
      <div className="hero">
        <div className="hero-scan" />
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>{heading.split(' ')[0]} <span className="accent-text">{heading.split(' ').slice(1).join(' ') || 'de Segurança'}</span></h1>
            <div className="page-sub" style={{ marginTop: 4 }}>Central normalizada de achados · múltiplos scanners · risco priorizado</div>
          </div>
        </div>
      </div>

      {canWrite && (
        <Card title="Ingerir resultado de scan (Trivy JSON)">
          <div className="row" style={{ gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div className="field" style={{ width: 200 }}>
              <label>Ambiente</label>
              <input value={ingestEnv} onChange={(e) => setIngestEnv(e.target.value)} placeholder="production" />
            </div>
            <button className="primary btn-icon" disabled={ingest.isPending} onClick={() => fileRef.current?.click()}>
              <Icon name="download" size={15} /> {ingest.isPending ? 'Processando…' : 'Selecionar arquivo Trivy'}
            </button>
            <input ref={fileRef} type="file" accept=".json,application/json" style={{ display: 'none' }} onChange={onFile} />
            <span className="muted" style={{ fontSize: 12 }}>Gere com: <span className="mono">trivy image -f json -o out.json IMAGEM</span></span>
          </div>
          {ingestMsg && <div className="muted" style={{ fontSize: 12, marginTop: 8, color: ingestMsg.startsWith('Falha') ? 'var(--critical)' : 'var(--low)' }}>{ingestMsg}</div>}
        </Card>
      )}

      {/* Filtros */}
      <Card>
        <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
          <input placeholder="Buscar título, ativo, CVE, pacote…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} style={{ flex: 1, minWidth: 200 }} />
          <select value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1) }} style={{ width: 150 }}>
            <option value="">Toda severidade</option>
            {['critical', 'high', 'medium', 'low', 'info'].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} style={{ width: 150 }}>
            <option value="open">Abertos</option>
            <option value="suppressed">Suprimidos</option>
            <option value="resolved">Resolvidos</option>
          </select>
          <input placeholder="Ambiente" value={env} onChange={(e) => { setEnv(e.target.value); setPage(1) }} style={{ width: 140 }} />
        </div>
      </Card>

      {list.isLoading && <Loading />}
      {list.data && (
        <Card className="table-wrap" title={`${list.data.total} achado(s)`}>
          <table>
            <thead><tr><th>Risco</th><th>Severidade</th><th>Título</th><th>Ativo</th><th>CVE / Pacote</th><th>Fonte</th><th>Visto</th><th></th></tr></thead>
            <tbody>
              {list.data.items.map((f) => (
                <tr key={f.id}>
                  <td><span style={{ display: 'inline-block', minWidth: 34, textAlign: 'center', fontWeight: 800, color: BAND[f.risk_band] }}>{f.risk_score}</span></td>
                  <td><Badge kind={SEV_KIND[f.severity]}>{f.severity}</Badge></td>
                  <td>{f.title}{f.occurrences > 1 && <span className="muted" style={{ fontSize: 11 }}> ×{f.occurrences}</span>}</td>
                  <td className="mono" style={{ fontSize: 12 }}>{f.asset_name}<div className="muted" style={{ fontSize: 10 }}>{f.asset_type} · {f.environment}</div></td>
                  <td className="mono muted" style={{ fontSize: 11 }}>{f.cve || '—'}{f.package_name ? <div>{f.package_name}{f.fixed_version ? ` → ${f.fixed_version}` : ''}</div> : ''}</td>
                  <td className="muted">{f.source_tool}</td>
                  <td className="mono muted" style={{ fontSize: 11 }}>{relative(f.last_seen)}</td>
                  <td><button style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => setOpenId(f.id)}>Ver</button></td>
                </tr>
              ))}
              {!list.data.items.length && <tr><td colSpan={8} className="muted">Nenhum achado para este filtro. Ingira um scan acima.</td></tr>}
            </tbody>
          </table>
          {list.data.total > 50 && (
            <div className="row" style={{ marginTop: 10, gap: 8, justifyContent: 'center' }}>
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>← Anterior</button>
              <span className="muted" style={{ fontSize: 12 }}>Página {page} de {Math.ceil(list.data.total / 50)}</span>
              <button disabled={page >= Math.ceil(list.data.total / 50)} onClick={() => setPage((p) => p + 1)}>Próxima →</button>
            </div>
          )}
        </Card>
      )}

      {openId != null && detail.data && (
        <Card title={detail.data.title}>
          <button style={{ float: 'right' }} onClick={() => setOpenId(null)}>Fechar</button>
          <div className="row" style={{ gap: 12, marginBottom: 10, flexWrap: 'wrap' }}>
            <Badge kind={SEV_KIND[detail.data.severity]}>{detail.data.severity}</Badge>
            <span style={{ fontWeight: 800, color: BAND[detail.data.risk_band] }}>risco {detail.data.risk_score}</span>
            <span className="muted mono" style={{ fontSize: 12 }}>{detail.data.category} · {detail.data.asset_type}</span>
            {detail.data.cve && <Badge kind="high">{detail.data.cve}</Badge>}
            {detail.data.cvss != null && <span className="muted">CVSS {detail.data.cvss}</span>}
            {detail.data.status === 'suppressed' && <Badge kind="low">suprimido até {fmtDate(detail.data.suppressed_until)}</Badge>}
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.8 }}>
            <div><span className="muted">Ativo:</span> <span className="mono">{detail.data.asset_name}</span> · {detail.data.environment}</div>
            {detail.data.package_name && <div><span className="muted">Pacote:</span> <span className="mono">{detail.data.package_name} {detail.data.installed_version} → {detail.data.fixed_version || '(sem correção)'}</span></div>}
            {detail.data.file_path && <div><span className="muted">Arquivo:</span> <span className="mono">{detail.data.file_path}</span></div>}
            {detail.data.description && <div style={{ marginTop: 6 }}>{detail.data.description}</div>}
            {detail.data.remediation && <div style={{ marginTop: 6 }}><span className="muted">Remediação:</span> {detail.data.remediation}</div>}
            {detail.data.evidence && Object.keys(detail.data.evidence).length > 0 && (
              <div style={{ marginTop: 6 }}><span className="muted">Evidência (mascarada):</span> <span className="mono" style={{ fontSize: 12 }}>{JSON.stringify(detail.data.evidence)}</span></div>
            )}
            {!!detail.data.references?.length && (
              <div style={{ marginTop: 6 }}><span className="muted">Referências:</span> {detail.data.references.slice(0, 5).map((r) => <a key={r} href={r} target="_blank" rel="noreferrer" style={{ marginRight: 8, fontSize: 12 }}>link</a>)}</div>
            )}
          </div>
          {canWrite && (
            <div style={{ marginTop: 14, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
              <div className="row" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                {['in_progress', 'fixed', 'wont_fix'].map((st) => (
                  <button key={st} disabled={setState.isPending} onClick={() => setState.mutate({ id: detail.data!.id, state: st })}>
                    {st === 'in_progress' ? 'Em correção' : st === 'fixed' ? 'Marcar corrigido' : 'Não corrigir'}
                  </button>
                ))}
              </div>
              <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                <input placeholder="Motivo da supressão (auditado)" value={supReason} onChange={(e) => setSupReason(e.target.value)} style={{ flex: 1, minWidth: 220 }} />
                <button disabled={suppress.isPending || supReason.trim().length < 5} onClick={() => suppress.mutate({ id: detail.data!.id, reason: supReason.trim(), days: 30 })}>Suprimir 30d</button>
              </div>
            </div>
          )}
        </Card>
      )}
    </>
  )
}
