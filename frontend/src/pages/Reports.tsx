import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { fmtDate } from '@/lib/format'
import { Card, Loading } from '@/components/ui'
import { Icon, IconName } from '@/components/icons'

interface ReportMeta {
  key: string; title: string; description: string; category: string
  icon: string; supports_dates: boolean; summary: boolean
}
interface ReportData {
  key: string; title: string; category: string
  columns: { field: string; header: string }[]
  rows: Record<string, unknown>[]
  total: number; summary?: Record<string, unknown>; generated_at: string
  preview_truncated?: boolean
}

const CAT_ICON: Record<string, IconName> = {
  Executivo: 'posture', Segurança: 'target', Identidade: 'users',
  Eventos: 'list', Conformidade: 'report',
}

function fmtCell(v: unknown): string {
  if (v === true) return 'Sim'
  if (v === false) return 'Não'
  if (v === null || v === undefined || v === '') return '—'
  const s = String(v)
  if (/^\d{4}-\d{2}-\d{2}T/.test(s)) return fmtDate(s)
  return s
}

export function Reports() {
  const { data: list, isLoading } = useQuery({
    queryKey: ['reports-list'],
    queryFn: () => api.get<{ categories: string[]; reports: ReportMeta[] }>('/reports'),
  })
  const [sel, setSel] = useState<ReportMeta | null>(null)
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [busy, setBusy] = useState(false)
  const [chatWh, setChatWh] = useState('')
  const [chatMsg, setChatMsg] = useState('')

  const webhooks = useQuery({
    queryKey: ['chat-webhooks'],
    queryFn: () => api.get<{ items: { id: number; name: string; enabled: boolean }[] }>('/chat-webhooks'),
  })

  async function sendChat() {
    if (!sel || !chatWh) return
    setBusy(true); setChatMsg('')
    try {
      const r = await api.post<{ webhook: string }>(`/reports/${sel.key}/send-chat?webhook_id=${chatWh}`)
      setChatMsg(`Resumo enviado ao canal ${r.webhook}.`)
    } catch (e) {
      setChatMsg('Falha: ' + (e as Error).message)
    } finally { setBusy(false) }
  }

  const preview = useQuery({
    queryKey: ['report-preview', sel?.key, from, to],
    queryFn: () => {
      const p = new URLSearchParams()
      if (from) p.set('date_from', new Date(from).toISOString())
      if (to) p.set('date_to', new Date(to).toISOString())
      return api.get<ReportData>(`/reports/${sel!.key}/preview?${p.toString()}`)
    },
    enabled: !!sel,
  })

  async function download(fmt: 'csv' | 'json') {
    if (!sel) return
    setBusy(true)
    try {
      const p = new URLSearchParams({ key: sel.key, fmt })
      if (from) p.set('date_from', new Date(from).toISOString())
      if (to) p.set('date_to', new Date(to).toISOString())
      const blob = await api.download(`/reports/export?${p.toString()}`, {})
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `${sel.key}.${fmt}`; a.click()
      URL.revokeObjectURL(url)
    } finally { setBusy(false) }
  }

  function openHtml() {
    if (!preview.data) return
    const d = preview.data
    const cols = d.columns
    // Cor do relatório segue o tema selecionado (Dante/Vergil).
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent-deep').trim() || '#b00d22'
    const summaryHtml = d.summary
      ? `<div class="summary">${Object.entries(d.summary).map(([k, v]) =>
          `<div class="kpi"><div class="v">${v ?? '—'}</div><div class="l">${k.replace(/_/g, ' ')}</div></div>`).join('')}</div>`
      : ''
    const rows = d.rows.map((r) =>
      `<tr>${cols.map((c) => `<td>${fmtCell(r[c.field]).replace(/</g, '&lt;')}</td>`).join('')}</tr>`).join('')
    const html = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>${d.title}</title>
      <style>
        *{box-sizing:border-box} body{font-family:Segoe UI,system-ui,sans-serif;color:#1a1a1a;margin:0;padding:32px;background:#fff}
        .hd{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:3px solid ${accent};padding-bottom:12px;margin-bottom:18px}
        .hd h1{margin:0;font-size:22px;color:#0a0a0a} .hd .brand{font-weight:800;color:${accent};letter-spacing:1px}
        .meta{color:#666;font-size:12px}
        .summary{display:flex;gap:14px;flex-wrap:wrap;margin:0 0 20px}
        .kpi{border:1px solid #e2e2e2;border-radius:8px;padding:10px 16px;min-width:120px}
        .kpi .v{font-size:24px;font-weight:800;color:${accent}} .kpi .l{font-size:11px;color:#666;text-transform:capitalize}
        table{width:100%;border-collapse:collapse;font-size:12px}
        th{background:#f4f4f4;text-align:left;padding:8px 10px;border-bottom:2px solid #ddd;font-size:11px;text-transform:uppercase;letter-spacing:.4px}
        td{padding:7px 10px;border-bottom:1px solid #eee}
        tr:nth-child(even) td{background:#fafafa}
        .ft{margin-top:20px;color:#999;font-size:10px;border-top:1px solid #eee;padding-top:8px}
        @media print{body{padding:12px}.noprint{display:none}}
        .noprint{margin-bottom:16px}
        .btn{background:${accent};color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px}
      </style></head><body>
      <div class="noprint"><button class="btn" onclick="window.print()">Imprimir / Salvar PDF</button></div>
      <div class="hd"><div><div class="brand">AD·AUDIT</div><h1>${d.title}</h1></div>
        <div class="meta">Gerado em ${new Date(d.generated_at).toLocaleString('pt-BR')}<br>${d.total} registro(s) · ${d.category}</div></div>
      ${summaryHtml}
      <table><thead><tr>${cols.map((c) => `<th>${c.header}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>
      ${d.preview_truncated ? '<div class="ft">Prévia limitada a 200 registros. Use CSV para o conjunto completo.</div>' : ''}
      <div class="ft">AD Audit Portal — relatório interno · uso restrito</div>
      </body></html>`
    const w = window.open('', '_blank')
    if (w) { w.document.write(html); w.document.close() }
  }

  if (isLoading || !list) return <Loading />

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Relatórios</div>
          <div className="page-sub">Gere, visualize e exporte (CSV, JSON ou PDF via impressão)</div>
        </div>
      </div>

      {!sel && list.categories.map((cat) => (
        <div key={cat}>
          <div className="section-title">{cat}</div>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
            {list.reports.filter((r) => r.category === cat).map((r) => (
              <button key={r.key} className="card report-card" onClick={() => { setSel(r); setFrom(''); setTo('') }}>
                <div className="report-ic"><Icon name={(r.icon as IconName) || CAT_ICON[cat]} size={22} /></div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, marginBottom: 3 }}>{r.title}</div>
                  <div className="muted" style={{ fontSize: 12 }}>{r.description}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      ))}

      {sel && (
        <>
          <button className="btn-icon" style={{ marginBottom: 12 }} onClick={() => setSel(null)}>
            <Icon name="collapse" size={15} /> Voltar à galeria
          </button>
          <Card>
            <div className="row" style={{ alignItems: 'flex-start' }}>
              <div className="report-ic"><Icon name={sel.icon as IconName} size={22} /></div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 16, fontWeight: 700 }}>{sel.title}</div>
                <div className="muted" style={{ fontSize: 13 }}>{sel.description}</div>
              </div>
            </div>
            <div className="row" style={{ marginTop: 14, alignItems: 'flex-end' }}>
              {sel.supports_dates && (
                <>
                  <div><label className="muted" style={{ fontSize: 11 }}>De</label><input type="date" value={from} onChange={(e) => setFrom(e.target.value)} style={{ width: 160 }} /></div>
                  <div><label className="muted" style={{ fontSize: 11 }}>Até</label><input type="date" value={to} onChange={(e) => setTo(e.target.value)} style={{ width: 160 }} /></div>
                </>
              )}
              <span className="spacer" />
              <button className="btn-icon" onClick={openHtml} disabled={!preview.data}><Icon name="external" size={15} /> Abrir / PDF</button>
              <button className="btn-icon" onClick={() => download('csv')} disabled={busy}><Icon name="download" size={15} /> CSV</button>
              <button className="btn-icon" onClick={() => download('json')} disabled={busy}><Icon name="download" size={15} /> JSON</button>
            </div>
            {(webhooks.data?.items.filter((w) => w.enabled).length ?? 0) > 0 && (
              <div className="row" style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
                <Icon name="megaphone" size={16} style={{ color: 'var(--accent-2)' }} />
                <span className="muted" style={{ fontSize: 12 }}>Enviar resumo para o Google Chat:</span>
                <select value={chatWh} onChange={(e) => setChatWh(e.target.value)} style={{ width: 200 }}>
                  <option value="">Selecione o canal…</option>
                  {webhooks.data?.items.filter((w) => w.enabled).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                </select>
                <button className="btn-icon primary" disabled={!chatWh || busy} onClick={sendChat}><Icon name="send" size={14} /> Enviar</button>
                {chatMsg && <span className="muted" style={{ fontSize: 12 }}>{chatMsg}</span>}
              </div>
            )}
          </Card>

          {preview.isLoading && <Loading />}
          {preview.data && (
            <>
              {preview.data.summary && (
                <div className="grid kpi-row" style={{ marginTop: 14 }}>
                  {Object.entries(preview.data.summary).map(([k, v]) => (
                    <div className="card" key={k}>
                      <div className="kpi-value" style={{ fontSize: 24 }}>{String(v ?? '—')}</div>
                      <div className="kpi-label" style={{ textTransform: 'capitalize' }}>{k.replace(/_/g, ' ')}</div>
                    </div>
                  ))}
                </div>
              )}
              <Card className="table-wrap" title={`${preview.data.total} registro(s)${preview.data.preview_truncated ? ' (prévia: 200)' : ''}`}>
                <table>
                  <thead><tr>{preview.data.columns.map((c) => <th key={c.field}>{c.header}</th>)}</tr></thead>
                  <tbody>
                    {preview.data.rows.map((r, i) => (
                      <tr key={i}>{preview.data!.columns.map((c) => <td key={c.field} className={c.field.includes('risk') ? '' : 'mono'} style={{ fontSize: 12 }}>{fmtCell(r[c.field])}</td>)}</tr>
                    ))}
                    {!preview.data.rows.length && <tr><td colSpan={preview.data.columns.length} className="muted">Sem dados para este relatório/período.</td></tr>}
                  </tbody>
                </table>
              </Card>
            </>
          )}
        </>
      )}
    </>
  )
}
