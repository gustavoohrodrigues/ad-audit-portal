import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { Badge, Card, Loading } from '@/components/ui'

interface Item { id: number; entity_type: string; entity_ref: string; note?: string }
interface WL { id: number; name: string; description?: string; owner: string; items: Item[] }

export function Watchlists() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['watchlists'],
    queryFn: () => api.get<{ watchlists: WL[] }>('/watchlists'),
  })
  const [name, setName] = useState('')
  const [newItem, setNewItem] = useState<Record<number, { type: string; ref: string }>>({})

  const createList = useMutation({
    mutationFn: () => api.post('/watchlists', { name }),
    onSuccess: () => { setName(''); qc.invalidateQueries({ queryKey: ['watchlists'] }) },
  })
  const addItem = useMutation({
    mutationFn: ({ id, type, ref }: { id: number; type: string; ref: string }) =>
      api.post(`/watchlists/${id}/items`, { entity_type: type, entity_ref: ref }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlists'] }),
  })
  const delItem = useMutation({
    mutationFn: ({ id, itemId }: { id: number; itemId: number }) =>
      api.del(`/watchlists/${id}/items/${itemId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlists'] }),
  })

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Watchlists</div>
          <div className="page-sub">Listas de entidades monitoradas (contas, grupos, computadores)</div>
        </div>
      </div>

      <Card title="Nova watchlist">
        <form className="row" onSubmit={(e) => { e.preventDefault(); if (name.trim()) createList.mutate() }}>
          <input placeholder="Nome da lista…" value={name} onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
          <button className="primary" type="submit" disabled={!name.trim()}>Criar</button>
        </form>
      </Card>

      {isLoading && <Loading />}
      {data?.watchlists.map((wl) => {
        const draft = newItem[wl.id] || { type: 'user', ref: '' }
        return (
          <Card key={wl.id} title={wl.name}>
            <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>por {wl.owner} · {wl.items.length} item(ns)</div>
            {wl.items.map((it) => (
              <div key={it.id} className="row" style={{ padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
                <Badge kind="info">{it.entity_type}</Badge>
                {it.entity_type === 'user'
                  ? <Link to={`/users/${encodeURIComponent(it.entity_ref)}`} className="mono">{it.entity_ref}</Link>
                  : <span className="mono">{it.entity_ref}</span>}
                <span className="spacer" />
                <button style={{ padding: '2px 8px', fontSize: 11 }} onClick={() => delItem.mutate({ id: wl.id, itemId: it.id })}>Remover</button>
              </div>
            ))}
            <form
              className="row"
              style={{ marginTop: 10 }}
              onSubmit={(e) => { e.preventDefault(); if (draft.ref.trim()) { addItem.mutate({ id: wl.id, type: draft.type, ref: draft.ref.trim() }); setNewItem((s) => ({ ...s, [wl.id]: { type: draft.type, ref: '' } })) } }}
            >
              <select value={draft.type} onChange={(e) => setNewItem((s) => ({ ...s, [wl.id]: { ...draft, type: e.target.value } }))} style={{ width: 140 }}>
                <option value="user">Usuário</option>
                <option value="group">Grupo</option>
                <option value="computer">Computador</option>
              </select>
              <input placeholder="sAMAccountName…" value={draft.ref} onChange={(e) => setNewItem((s) => ({ ...s, [wl.id]: { ...draft, ref: e.target.value } }))} style={{ flex: 1 }} />
              <button type="submit">Adicionar</button>
            </form>
          </Card>
        )
      })}
      {data && !data.watchlists.length && <div className="muted" style={{ padding: 20 }}>Nenhuma watchlist ainda. Crie a primeira acima.</div>}
    </>
  )
}
