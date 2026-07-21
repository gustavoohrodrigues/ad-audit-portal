import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { Badge, Card, Loading } from '@/components/ui'

interface Group {
  sam_account_name: string; display_name?: string; description?: string
  member_count: number; is_privileged: boolean; admin_count?: number
}
interface GroupList { total: number; privileged_total: number; count: number; items: Group[] }
interface GroupDetail {
  sam_account_name: string; display_name?: string; description?: string
  is_privileged: boolean; member_count: number; members: string[]
}

export function Groups() {
  const [q, setQ] = useState('')
  const [term, setTerm] = useState('')
  const [onlyPriv, setOnlyPriv] = useState(false)
  const [sel, setSel] = useState<string | null>(null)

  const params = new URLSearchParams({ limit: '150' })
  if (term) params.set('q', term)
  if (onlyPriv) params.set('privileged', 'true')

  const list = useQuery({
    queryKey: ['groups', term, onlyPriv],
    queryFn: () => api.get<GroupList>(`/groups?${params.toString()}`),
  })
  const detail = useQuery({
    queryKey: ['group', sel],
    queryFn: () => api.get<GroupDetail>(`/groups/${encodeURIComponent(sel!)}`),
    enabled: !!sel,
  })

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Grupos</div>
          <div className="page-sub">
            {list.data ? `${list.data.total} grupos · ${list.data.privileged_total} privilegiados` : 'sincronizados do AD'}
          </div>
        </div>
      </div>

      <Card>
        <form className="row" onSubmit={(e) => { e.preventDefault(); setTerm(q.trim()) }}>
          <input placeholder="Buscar grupo…" value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: 1 }} />
          <label className="row" style={{ gap: 6 }}>
            <input type="checkbox" checked={onlyPriv} onChange={(e) => setOnlyPriv(e.target.checked)} style={{ width: 'auto' }} />
            <span className="muted">só privilegiados</span>
          </label>
          <button className="primary" type="submit">Buscar</button>
        </form>
      </Card>

      <div className="grid" style={{ gridTemplateColumns: sel ? '1fr 380px' : '1fr' }}>
        <Card className="table-wrap">
          {list.isLoading && <Loading />}
          {list.data && (
            <table>
              <thead><tr><th>Grupo</th><th>Descrição</th><th>Membros</th><th></th></tr></thead>
              <tbody>
                {list.data.items.map((g) => (
                  <tr key={g.sam_account_name}>
                    <td>
                      <span className="mono">{g.sam_account_name}</span>{' '}
                      {g.is_privileged && <Badge kind="priv">privilegiado</Badge>}
                    </td>
                    <td className="muted">{g.description || '—'}</td>
                    <td>{g.member_count}</td>
                    <td><button onClick={() => setSel(g.sam_account_name)} style={{ padding: '4px 8px' }}>Membros</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {sel && (
          <Card title={`Membros · ${sel}`}>
            <button onClick={() => setSel(null)} style={{ float: 'right' }}>Fechar</button>
            {detail.isLoading && <Loading />}
            {detail.data && (
              <>
                {detail.data.is_privileged && <Badge kind="high">Grupo privilegiado</Badge>}
                <div style={{ marginTop: 10, maxHeight: 420, overflow: 'auto' }}>
                  {detail.data.members.map((m) => (
                    <div key={m} style={{ padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
                      <Link to={`/users/${encodeURIComponent(m)}`} className="mono">{m}</Link>
                    </div>
                  ))}
                  {!detail.data.members.length && <div className="muted">Sem membros diretos.</div>}
                </div>
              </>
            )}
          </Card>
        )}
      </div>
    </>
  )
}
