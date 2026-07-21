import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { Badge, Card, Loading } from '@/components/ui'
import type { ADUser } from '@/types'

function ExpiryChip({ user }: { user: ADUser }) {
  if (user.password_never_expires || !user.password_expires_at) return null
  const days = Math.ceil((new Date(user.password_expires_at).getTime() - Date.now()) / 86400000)
  if (days < 0) return <Badge kind="critical">senha expirada</Badge>
  if (days <= 7) return <Badge kind="high">expira {days}d ⚠</Badge>
  if (days <= 14) return <Badge kind="medium">expira {days}d</Badge>
  return null
}

export function UserSearch() {
  const [q, setQ] = useState('')
  const [term, setTerm] = useState('')

  const { data, isFetching } = useQuery({
    queryKey: ['user-search', term],
    queryFn: () => api.get<{ items: ADUser[]; count: number }>(`/users/search?q=${encodeURIComponent(term)}`),
    enabled: term.length >= 1,
  })

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Pesquisa de Usuários</div>
          <div className="page-sub">sAMAccountName · nome · e-mail · UPN · SID · DN</div>
        </div>
      </div>
      <Card>
        <form onSubmit={(e) => { e.preventDefault(); setTerm(q.trim()) }} className="row">
          <input placeholder="Buscar usuário…" value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: 1 }} />
          <button className="primary" type="submit">Buscar</button>
        </form>
      </Card>

      {isFetching && <Loading />}
      {data && (
        <Card title={`${data.count} resultado(s)`} className="table-wrap">
          <table>
            <thead>
              <tr><th>Login</th><th>Nome</th><th>Departamento</th><th>Status</th><th>Flags</th></tr>
            </thead>
            <tbody>
              {data.items.map((u) => (
                <tr key={u.sam_account_name}>
                  <td><Link to={`/users/${encodeURIComponent(u.sam_account_name)}`} className="mono">{u.sam_account_name}</Link></td>
                  <td>{u.display_name || '—'}</td>
                  <td>{u.department || '—'}</td>
                  <td>
                    {u.is_locked ? <Badge kind="critical">Bloqueado</Badge> : u.is_disabled ? <Badge kind="medium">Desabilitado</Badge> : <Badge kind="low">Ativo</Badge>}
                  </td>
                  <td>
                    <div className="chips">
                      {u.is_privileged && <Badge kind="priv">Privilegiado</Badge>}
                      {u.is_critical && <Badge kind="crit-acct">Crítico</Badge>}
                      <ExpiryChip user={u} />
                      {u.is_inactive && <Badge kind="info">Inativo</Badge>}
                    </div>
                  </td>
                </tr>
              ))}
              {!data.items.length && <tr><td colSpan={5} className="muted">Nenhum usuário encontrado.</td></tr>}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
