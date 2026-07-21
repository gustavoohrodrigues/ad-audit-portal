import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Badge, Card } from '@/components/ui'
import { useAuth } from '@/hooks/useAuth'

interface Webhook { id: number; name: string; provider: string; url_masked: string; enabled: boolean; created_by?: string }

export function ChatWebhooks() {
  const qc = useQueryClient()
  const { can } = useAuth()
  const isAdmin = can('*')
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [err, setErr] = useState('')

  const list = useQuery({ queryKey: ['chat-webhooks'], queryFn: () => api.get<{ items: Webhook[] }>('/chat-webhooks') })
  const create = useMutation({
    mutationFn: () => api.post('/chat-webhooks', { name, url, provider: 'google_chat' }),
    onSuccess: () => { setName(''); setUrl(''); setErr(''); qc.invalidateQueries({ queryKey: ['chat-webhooks'] }) },
    onError: (e) => setErr((e as Error).message),
  })
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/chat-webhooks/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['chat-webhooks'] }),
  })

  return (
    <Card title="Google Chat — cadastro de espaços (webhook)">
      <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
        Cole a URL do <strong>Incoming Webhook</strong> do espaço no Google Chat
        (Espaço → Apps e integrações → Webhooks → Adicionar). A URL é armazenada
        de forma mascarada e usada pela Central de Mensagens.
      </div>

      {list.data?.items.map((w) => (
        <div key={w.id} className="row" style={{ padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
          <Badge kind="info">{w.provider}</Badge>
          <strong>{w.name}</strong>
          <span className="mono muted" style={{ fontSize: 11 }}>{w.url_masked}</span>
          <span className="spacer" />
          {w.enabled ? <Badge kind="low">ativo</Badge> : <Badge kind="medium">inativo</Badge>}
          {isAdmin && <button style={{ padding: '2px 8px', fontSize: 11 }} onClick={() => remove.mutate(w.id)}>Remover</button>}
        </div>
      ))}
      {!list.data?.items.length && <div className="muted" style={{ fontSize: 12 }}>Nenhum espaço cadastrado.</div>}

      {isAdmin && (
        <form className="row" style={{ marginTop: 14, alignItems: 'flex-end' }} onSubmit={(e) => { e.preventDefault(); if (name && url) create.mutate() }}>
          <div style={{ flex: '0 0 180px' }}>
            <label className="muted" style={{ fontSize: 11 }}>Nome do espaço</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: SOC-Alertas" />
          </div>
          <div style={{ flex: 1 }}>
            <label className="muted" style={{ fontSize: 11 }}>URL do webhook (https://chat.googleapis.com/…)</label>
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://chat.googleapis.com/v1/spaces/…/messages?key=…&token=…" />
          </div>
          <button className="primary" type="submit" disabled={!name || !url || create.isPending}>Cadastrar</button>
        </form>
      )}
      {err && <div className="error" style={{ marginTop: 8 }}>{err}</div>}
    </Card>
  )
}
