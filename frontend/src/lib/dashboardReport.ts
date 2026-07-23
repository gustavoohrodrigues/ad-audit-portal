// Gera relatórios imprimíveis (PDF) do Dashboard/Postura com gráficos em SVG
// embutidos (donut + sparklines) — sem dependência externa, abre em nova aba.

export interface ReportOpts {
  title: string
  subtitle?: string
  score?: { score: number; grade: string }
  kpis?: { label: string; value: number | string; tone?: string }[]
  categories?: { label: string; value: number; color: string }[]
  factors?: { label: string; count: number; impact: number; severity: string }[]
  trends?: { label: string; data: number[]; color: string }[]
}

const SEV: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e', info: '#38bdf8',
}

function esc(s?: string): string {
  return (s || '').replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c] || c))
}

function sparkSVG(data: number[], color: string, w = 240, h = 46): string {
  if (!data.length) return ''
  const max = Math.max(...data, 1)
  const min = Math.min(...data, 0)
  const span = max - min || 1
  const sx = data.length > 1 ? w / (data.length - 1) : w
  const y = (v: number) => h - 5 - ((v - min) / span) * (h - 10)
  const pts = data.map((v, i) => `${(i * sx).toFixed(1)},${y(v).toFixed(1)}`)
  const line = `M${pts.join(' L')}`
  const area = `${line} L${w},${h} L0,${h} Z`
  const last = data[data.length - 1]
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">`
    + `<path d="${area}" fill="${color}22"/><path d="${line}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>`
    + `<circle cx="${((data.length - 1) * sx).toFixed(1)}" cy="${y(last).toFixed(1)}" r="2.6" fill="${color}"/></svg>`
}

function annular(cx: number, cy: number, rO: number, rI: number, a0: number, a1: number): string {
  const p = (r: number, a: number): [number, number] => [cx + r * Math.cos(a), cy + r * Math.sin(a)]
  const [x0o, y0o] = p(rO, a0); const [x1o, y1o] = p(rO, a1)
  const [x0i, y0i] = p(rI, a1); const [x1i, y1i] = p(rI, a0)
  const large = a1 - a0 > Math.PI ? 1 : 0
  return `M${x0o.toFixed(2)} ${y0o.toFixed(2)} A${rO} ${rO} 0 ${large} 1 ${x1o.toFixed(2)} ${y1o.toFixed(2)} `
    + `L${x0i.toFixed(2)} ${y0i.toFixed(2)} A${rI} ${rI} 0 ${large} 0 ${x1i.toFixed(2)} ${y1i.toFixed(2)} Z`
}

function donutSVG(slices: { label: string; value: number; color: string }[], size = 210): string {
  const active = slices.filter((s) => s.value > 0)
  const total = active.reduce((s, x) => s + x.value, 0) || 1
  const cx = size / 2; const cy = size / 2; const rO = size / 2 - 4; const rI = rO * 0.62
  let a0 = -Math.PI / 2
  const seg = active.map((s) => {
    let frac = s.value / total
    if (frac > 0.9999) frac = 0.9999
    const a1 = a0 + frac * 2 * Math.PI
    const path = annular(cx, cy, rO, rI, a0, a1)
    a0 = a1
    return `<path d="${path}" fill="${s.color}"/>`
  }).join('')
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${seg}`
    + `<text x="${cx}" y="${cy - 1}" text-anchor="middle" font-size="26" font-weight="800" fill="#1a1a1a">${total}</text>`
    + `<text x="${cx}" y="${cy + 16}" text-anchor="middle" font-size="10" fill="#888">contas</text></svg>`
}

export function exportReport(opts: ReportOpts): void {
  const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent-deep').trim() || '#b00d22'
  const grade = opts.score
    ? `<div class="grade" style="border-color:${accent}"><div class="gv">${opts.score.grade}</div><div class="gl">${opts.score.score}/100</div></div>`
    : ''
  const kpis = opts.kpis?.length
    ? `<div class="kpis">${opts.kpis.map((k) => `<div class="kpi"><div class="v">${k.value}</div><div class="l">${esc(k.label)}</div></div>`).join('')}</div>`
    : ''
  const pie = opts.categories?.length
    ? `<div class="block"><h2>Distribuição de risco</h2><div class="pierow">${donutSVG(opts.categories)}
        <div class="legend">${opts.categories.filter((c) => c.value > 0).map((c) =>
          `<div class="lg"><span class="dot" style="background:${c.color}"></span>${esc(c.label)}<b>${c.value}</b></div>`).join('')}</div></div></div>`
    : ''
  const trends = opts.trends?.length
    ? `<div class="block"><h2>Tendências (14 dias)</h2><div class="sparks">${opts.trends.map((t) =>
        `<div class="spark"><div class="sl">${esc(t.label)}<b style="color:${t.color}">${t.data.length ? t.data[t.data.length - 1] : 0}</b></div>${sparkSVG(t.data, t.color)}</div>`).join('')}</div></div>`
    : ''
  const factors = opts.factors?.length
    ? `<div class="block"><h2>Fatores de risco</h2><table><thead><tr><th>Fator</th><th>Qtd.</th><th>Impacto</th><th>Severidade</th></tr></thead><tbody>${
        opts.factors.map((f) => `<tr><td>${esc(f.label)}</td><td>${f.count}</td><td>-${f.impact}</td><td><span class="sev" style="color:${SEV[f.severity] || '#666'}">${f.severity}</span></td></tr>`).join('')
      }</tbody></table></div>`
    : ''

  const html = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>${esc(opts.title)}</title><style>
    *{box-sizing:border-box}body{font-family:Segoe UI,system-ui,sans-serif;color:#1a1a1a;margin:0;padding:32px;background:#fff}
    .hd{border-bottom:3px solid ${accent};padding-bottom:12px;margin-bottom:18px;display:flex;justify-content:space-between;align-items:flex-end}
    .brand{font-weight:800;color:${accent};letter-spacing:1px} h1{margin:2px 0;font-size:22px} .meta{color:#666;font-size:12px;text-align:right}
    .grade{border:3px solid;border-radius:12px;padding:8px 16px;text-align:center} .grade .gv{font-size:30px;font-weight:800;color:${accent}} .grade .gl{font-size:11px;color:#666}
    .toprow{display:flex;gap:18px;align-items:center;margin-bottom:8px}
    .kpis{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 8px} .kpi{border:1px solid #e4e4e4;border-radius:8px;padding:10px 16px;min-width:120px}
    .kpi .v{font-size:22px;font-weight:800;color:${accent}} .kpi .l{font-size:11px;color:#666}
    .block{margin-top:22px} h2{font-size:14px;margin:0 0 10px;border-left:4px solid ${accent};padding-left:8px}
    .pierow{display:flex;gap:24px;align-items:center;flex-wrap:wrap}
    .legend{font-size:13px} .lg{display:flex;align-items:center;gap:8px;padding:3px 0} .lg b{margin-left:auto;padding-left:20px} .dot{width:11px;height:11px;border-radius:3px;display:inline-block}
    .sparks{display:grid;grid-template-columns:repeat(2,1fr);gap:16px} .spark{border:1px solid #eee;border-radius:8px;padding:10px}
    .sl{display:flex;justify-content:space-between;font-size:12px;color:#555;margin-bottom:4px} .sl b{font-size:18px}
    table{width:100%;border-collapse:collapse;font-size:12px} th{background:#f4f4f4;text-align:left;padding:7px 10px;border-bottom:2px solid #ddd;font-size:11px;text-transform:uppercase}
    td{padding:6px 10px;border-bottom:1px solid #eee} .sev{font-weight:700;text-transform:capitalize}
    .ft{margin-top:22px;color:#999;font-size:10px;border-top:1px solid #eee;padding-top:8px} .btn{background:${accent};color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer}
    @media print{body{padding:12px}.noprint{display:none}}</style></head><body>
    <div class="noprint" style="margin-bottom:14px"><button class="btn" onclick="window.print()">Imprimir / Salvar PDF</button></div>
    <div class="hd"><div><div class="brand">AD·AUDIT</div><h1>${esc(opts.title)}</h1></div>
      <div class="meta">${esc(opts.subtitle || '')}<br>Gerado em ${new Date().toLocaleString('pt-BR')}</div></div>
    <div class="toprow">${grade}${kpis}</div>
    ${pie}${trends}${factors}
    <div class="ft">AD Audit Portal — relatório interno · uso restrito</div></body></html>`
  const w = window.open('', '_blank')
  if (w) { w.document.write(html); w.document.close() }
}

export { SEV as REPORT_SEV }
