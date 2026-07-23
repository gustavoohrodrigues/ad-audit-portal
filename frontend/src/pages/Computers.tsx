import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { api } from '@/lib/api'
import { fmtDate } from '@/lib/format'
import { Badge, Card, Loading } from '@/components/ui'
import { useThemeColors } from '@/hooks/useAccent'

interface Computer {
  sam_account_name: string; dns_host_name?: string; operating_system?: string
  last_logon_timestamp?: string; when_created?: string; is_disabled: boolean
}
interface ComputerList {
  total: number; os_distribution: { os: string; count: number }[]; count: number; items: Computer[]
}

const LEGACY = /windows (7|8|xp|vista|server 2003|server 2008)/i

export function Computers() {
  const { accent } = useThemeColors()
  const [q, setQ] = useState('')
  const [term, setTerm] = useState('')
  const [selectedOs, setSelectedOs] = useState<string | null>(null)

  // agregado (sempre sobre o total) para o gráfico
  const agg = useQuery({
    queryKey: ['computers-agg'],
    queryFn: () => api.get<ComputerList>('/computers?limit=1'),
  })
  // lista, filtrada por SO (ao clicar numa barra) e/ou busca textual
  const params = new URLSearchParams({ limit: '300' })
  if (term) params.set('q', term)
  if (selectedOs) params.set('os', selectedOs)
  const list = useQuery({
    queryKey: ['computers-list', term, selectedOs],
    queryFn: () => api.get<ComputerList>(`/computers?${params.toString()}`),
  })

  const chart = (agg.data?.os_distribution || []).slice(0, 12).map((o) => ({
    os: (o.os || 'Desconhecido').replace('Windows ', 'Win '),
    fullOs: o.os || 'Desconhecido',
    count: o.count,
    legacy: LEGACY.test(o.os || ''),
  }))
  const legacyCount = (agg.data?.os_distribution || []).filter((o) => LEGACY.test(o.os || '')).reduce((s, o) => s + o.count, 0)

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Computadores</div>
          <div className="page-sub">{agg.data ? `${agg.data.total} máquinas sincronizadas` : 'sincronizados do AD'}</div>
        </div>
        {legacyCount > 0 && <Badge kind="high">{legacyCount} com SO legado</Badge>}
      </div>

      {agg.data && (
        <Card title="Distribuição por sistema operacional · clique numa barra para listar">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chart} layout="vertical" margin={{ left: 40 }}>
              <CartesianGrid stroke="var(--grid)" horizontal={false} />
              <XAxis type="number" stroke="var(--text-2)" fontSize={11} allowDecimals={false} />
              <YAxis type="category" dataKey="os" stroke="var(--text-2)" fontSize={11} width={90} />
              <Tooltip contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-bright)', borderRadius: 8 }} cursor={{ fill: `${accent}14` }} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]} cursor="pointer"
                onClick={(d) => { const p = d as unknown as { fullOs: string }; setSelectedOs(p.fullOs); setTerm(''); setQ('') }}>
                {chart.map((c, i) => (
                  <Cell key={i} fill={selectedOs === c.fullOs ? '#fff' : c.legacy ? '#ff7a2d' : accent} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="muted" style={{ fontSize: 11 }}>Barras laranja = sistemas legados/sem suporte. Clique para ver os computadores.</div>
        </Card>
      )}

      <Card>
        <form className="row" onSubmit={(e) => { e.preventDefault(); setSelectedOs(null); setTerm(q.trim()) }}>
          <input placeholder="Buscar por nome, DNS ou SO…" value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: 1 }} />
          <button className="primary" type="submit">Buscar</button>
        </form>
        {selectedOs && (
          <div className="row" style={{ marginTop: 10 }}>
            <span className="muted">Filtrando por SO:</span>
            <Badge kind="priv">{selectedOs}</Badge>
            <button style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => setSelectedOs(null)}>Limpar filtro ✕</button>
          </div>
        )}
      </Card>

      {list.isLoading && <Loading />}
      {list.data && (
        <Card className="table-wrap" title={selectedOs ? `${list.data.count} computador(es) com ${selectedOs}` : `${list.data.count} computador(es)`}>
          <table>
            <thead><tr><th>Nome</th><th>DNS</th><th>Sistema</th><th>Últ. logon</th><th>Status</th></tr></thead>
            <tbody>
              {list.data.items.map((c) => (
                <tr key={c.sam_account_name}>
                  <td className="mono">{c.sam_account_name}</td>
                  <td className="mono muted">{c.dns_host_name || '—'}</td>
                  <td>
                    {c.operating_system || '—'}{' '}
                    {c.operating_system && LEGACY.test(c.operating_system) && <Badge kind="high">legado</Badge>}
                  </td>
                  <td className="mono muted">{fmtDate(c.last_logon_timestamp)}</td>
                  <td>{c.is_disabled ? <Badge kind="low">desab.</Badge> : <Badge kind="low">ativo</Badge>}</td>
                </tr>
              ))}
              {!list.data.items.length && <tr><td colSpan={5} className="muted">Nenhum computador para este filtro.</td></tr>}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
