import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { fmtDate, relative } from '@/lib/format'
import { Badge, Card, Loading } from '@/components/ui'
import { Icon } from '@/components/icons'

interface Cfg {
  enabled: boolean
  profiles: { id: string; label: string; note: string }[]
  allowed_targets: string[]
  include_known_dcs: boolean
  suggested_targets: { host?: string; ip?: string }[]
  timeout_seconds: number
}
interface ScanRow {
  id: number; target: string; profile: string; status: string; requested_by?: string
  hosts_up: number; open_ports: number; risk_count: number; created_at: string
  finished_at?: string; error?: string
}
interface Port { port: number; proto: string; state: string; service: string; product: string; version: string }
interface Risk { severity: string; port: number; message: string }
interface Host { ip: string; hostname: string; ports: Port[]; risks: Risk[] }
interface ScanDetail extends ScanRow {
  summary: Record<string, number>; result: { hosts?: Host[] }
  started_at?: string
}

const ST: Record<string, { k: 'low' | 'medium' | 'high' | 'critical' | 'info'; label: string }> = {
  pending: { k: 'info', label: 'Na fila' },
  running: { k: 'medium', label: 'Executando' },
  done: { k: 'low', label: 'Concluído' },
  error: { k: 'critical', label: 'Erro' },
}

export function SecurityScan() {
  const qc = useQueryClient()
  const [target, setTarget] = useState('')
  const [profile, setProfile] = useState('quick')
  const [openId, setOpenId] = useState<number | null>(null)
  const [msg, setMsg] = useState('')

  const cfg = useQuery({ queryKey: ['scan-config'], queryFn: () => api.get<Cfg>('/security/scan-config') })
  const scans = useQuery({
    queryKey: ['scans'],
    queryFn: () => api.get<{ items: ScanRow[] }>('/security/scans'),
    refetchInterval: 5000,
  })
  const detail = useQuery({
    queryKey: ['scan', openId],
    queryFn: () => api.get<ScanDetail>(`/security/scans/${openId}`),
    enabled: openId != null,
    refetchInterval: openId != null ? 4000 : false,
  })
  const launch = useMutation({
    mutationFn: () => api.post<{ scan_id: number }>('/security/scans', { target: target.trim(), profile, confirm: true }),
    onSuccess: (r) => { setMsg(''); setOpenId(r.scan_id); qc.invalidateQueries({ queryKey: ['scans'] }) },
    onError: (e) => setMsg((e as Error).message),
  })

  if (cfg.isLoading || !cfg.data) return <Loading />
  const c = cfg.data

  return (
    <>
      <div className="hero">
        <div className="hero-scan" />
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Scan de <span className="accent-text">Segurança</span></h1>
            <div className="page-sub" style={{ marginTop: 4 }}>
              Varredura de portas/serviços (nmap) da infraestrutura autorizada · leitura, fora do AD
            </div>
          </div>
          <Badge kind={c.enabled ? 'low' : 'medium'}>{c.enabled ? 'Habilitado' : 'Desabilitado'}</Badge>
        </div>
      </div>

      {!c.enabled && (
        <div className="card" style={{ borderColor: 'var(--medium)', background: 'rgba(255,176,32,0.1)', marginBottom: 14 }}>
          <strong style={{ color: 'var(--medium)' }}>Módulo desabilitado</strong>
          <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
            Defina <span className="mono">SCAN_ENABLED=true</span> e a allowlist{' '}
            <span className="mono">SCAN_ALLOWED_TARGETS</span> no <span className="mono">.env</span> para liberar.
          </div>
        </div>
      )}

      {/* Lançar scan */}
      <Card title="Novo scan">
        <div className="grid" style={{ gridTemplateColumns: '1.4fr 1fr', gap: 14, alignItems: 'end' }}>
          <div className="field">
            <label>Alvo (hostname, IP ou CIDR autorizado)</label>
            <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="ex.: dc01.empresa.local ou 10.1.11.0/24" list="scan-targets" />
            <datalist id="scan-targets">
              {c.suggested_targets.map((t) => <option key={t.host || t.ip} value={t.host || t.ip} />)}
              {c.allowed_targets.map((t) => <option key={t} value={t} />)}
            </datalist>
          </div>
          <div className="field">
            <label>Perfil</label>
            <select value={profile} onChange={(e) => setProfile(e.target.value)}>
              {c.profiles.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </div>
        </div>
        <div className="muted" style={{ fontSize: 12, margin: '4px 0 12px' }}>
          {c.profiles.find((p) => p.id === profile)?.note}
        </div>
        {c.suggested_targets.length > 0 && (
          <div className="chips" style={{ marginBottom: 12 }}>
            {c.suggested_targets.slice(0, 8).map((t) => (
              <button key={t.host || t.ip} style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => setTarget(t.host || t.ip || '')}>
                {t.host || t.ip}
              </button>
            ))}
          </div>
        )}
        {msg && <div className="error" style={{ marginBottom: 10 }}>{msg}</div>}
        <button
          className="primary btn-icon"
          disabled={!c.enabled || launch.isPending || !target.trim()}
          onClick={() => { if (window.confirm(`Confirmar scan de "${target.trim()}" com o perfil "${profile}"? Esta é uma ação ativa e será auditada.`)) launch.mutate() }}
        >
          <Icon name="target" size={15} /> {launch.isPending ? 'Iniciando…' : 'Executar scan'}
        </button>
      </Card>

      {/* Histórico */}
      <Card title="Scans recentes" className="table-wrap">
        {scans.isLoading && <Loading />}
        {scans.data && !scans.data.items.length && <div className="muted">Nenhum scan executado ainda.</div>}
        {scans.data && scans.data.items.length > 0 && (
          <table>
            <thead><tr><th>Status</th><th>Alvo</th><th>Perfil</th><th>Hosts</th><th>Portas</th><th>Riscos</th><th>Quando</th><th>Por</th><th></th></tr></thead>
            <tbody>
              {scans.data.items.map((s) => (
                <tr key={s.id}>
                  <td><Badge kind={(ST[s.status] || ST.pending).k}>{(ST[s.status] || ST.pending).label}</Badge></td>
                  <td className="mono">{s.target}</td>
                  <td className="muted">{s.profile}</td>
                  <td>{s.hosts_up}</td>
                  <td>{s.open_ports}</td>
                  <td>{s.risk_count > 0 ? <Badge kind="high">{s.risk_count}</Badge> : <span className="muted">0</span>}</td>
                  <td className="mono muted">{relative(s.created_at)}</td>
                  <td className="muted mono" style={{ fontSize: 11 }}>{s.requested_by || '—'}</td>
                  <td><button style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => setOpenId(s.id)}>Ver</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Detalhe */}
      {openId != null && (
        <Card title={`Scan #${openId}${detail.data ? ` — ${detail.data.target}` : ''}`}>
          <button style={{ float: 'right' }} onClick={() => setOpenId(null)}>Fechar</button>
          {detail.isLoading && <Loading />}
          {detail.data && (
            <>
              <div className="row" style={{ gap: 16, marginBottom: 12, fontSize: 13 }}>
                <Badge kind={(ST[detail.data.status] || ST.pending).k}>{(ST[detail.data.status] || ST.pending).label}</Badge>
                <span className="muted">Iniciado {fmtDate(detail.data.started_at)}</span>
                {detail.data.finished_at && <span className="muted">· Concluído {fmtDate(detail.data.finished_at)}</span>}
              </div>
              {detail.data.status === 'running' && <div className="muted">Varredura em andamento…</div>}
              {detail.data.error && <div className="error">{detail.data.error}</div>}
              {(detail.data.result.hosts || []).map((h) => (
                <div key={h.ip || h.hostname} style={{ marginBottom: 16 }}>
                  <div className="section-title" style={{ marginTop: 0 }}>
                    {h.hostname || h.ip} <span className="muted mono" style={{ fontSize: 12 }}>{h.ip}</span>
                  </div>
                  {h.risks.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      {h.risks.map((r, i) => (
                        <div key={i} className="row" style={{ gap: 8, fontSize: 12, padding: '3px 0' }}>
                          <Badge kind={r.severity as 'low' | 'medium' | 'high' | 'critical'}>{r.severity}</Badge>
                          <span className="mono">:{r.port}</span>
                          <span className="muted">{r.message}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="table-wrap">
                    <table>
                      <thead><tr><th>Porta</th><th>Proto</th><th>Estado</th><th>Serviço</th><th>Produto / Versão</th></tr></thead>
                      <tbody>
                        {h.ports.map((p) => (
                          <tr key={`${p.port}-${p.proto}`}>
                            <td className="mono">{p.port}</td>
                            <td className="muted">{p.proto}</td>
                            <td>{p.state === 'open' ? <Badge kind="low">open</Badge> : <span className="muted">{p.state}</span>}</td>
                            <td>{p.service || '—'}</td>
                            <td className="muted">{[p.product, p.version].filter(Boolean).join(' ') || '—'}</td>
                          </tr>
                        ))}
                        {!h.ports.length && <tr><td colSpan={5} className="muted">Sem portas abertas.</td></tr>}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
              {detail.data.status === 'done' && !(detail.data.result.hosts || []).length && (
                <div className="muted">Nenhum host respondeu / nenhuma porta aberta encontrada.</div>
              )}
            </>
          )}
        </Card>
      )}
    </>
  )
}
