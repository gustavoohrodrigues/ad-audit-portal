import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Badge, Card } from '@/components/ui'
import { Icon } from '@/components/icons'
import { useAuth } from '@/hooks/useAuth'

interface Webhook {
  id: number; name: string; provider: string; url_masked: string
  enabled: boolean; health_alerts: boolean; created_by?: string
}

export function ChatWebhooks() {
  const qc = useQueryClient()
  const { can } = useAuth()
  const isAdmin = can('*')
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [err, setErr] = useState('')
  const [testResult, setTestResult] = useState<Record<number, { ok: boolean; msg: string }>>({})

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
  const patch = useMutation({
    mutationFn: ({ id, field, value }: { id: number; field: string; value: boolean }) =>
      api.patch(`/chat-webhooks/${id}?${field}=${value}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['chat-webhooks'] }),
  })

  async function test(id: number) {
    setTestResult((r) => ({ ...r, [id]: { ok: false, msg: 'enviando…' } }))
    try {
      await api.post(`/chat-webhooks/${id}/test`)
      setTestResult((r) => ({ ...r, [id]: { ok: true, msg: 'Card de teste enviado ao canal' } }))
    } catch (e) {
      setTestResult((r) => ({ ...r, [id]: { ok: false, msg: (e as Error).message } }))
    }
  }

  return (
    <Card title="Google Chat — canais e alertas">
      <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
        Cadastre o <strong>Incoming Webhook</strong> do espaço (Espaço → Apps e integrações → Webhooks).
        Canais com <strong>alertas de saúde</strong> ativos recebem cards automáticos quando o status vira crítico.
      </div>

      {list.data?.items.map((w) => (
        <div key={w.id} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
          <div className="row">
            <Icon name="integrations" size={16} style={{ color: 'var(--accent-2)' }} />
            <strong>{w.name}</strong>
            <span className="mono muted" style={{ fontSize: 11 }}>{w.url_masked}</span>
            <span className="spacer" />
            {w.enabled ? <Badge kind="low">ativo</Badge> : <Badge kind="medium">inativo</Badge>}
          </div>
          <div className="row" style={{ marginTop: 8, gap: 14 }}>
            {isAdmin && (
              <label className="row" style={{ gap: 6, cursor: 'pointer' }}>
                <input type="checkbox" checked={w.health_alerts} onChange={(e) => patch.mutate({ id: w.id, field: 'health_alerts', value: e.target.checked })} style={{ width: 'auto' }} />
                <span className="muted" style={{ fontSize: 12 }}>alertas de saúde</span>
              </label>
            )}
            {isAdmin && (
              <label className="row" style={{ gap: 6, cursor: 'pointer' }}>
                <input type="checkbox" checked={w.enabled} onChange={(e) => patch.mutate({ id: w.id, field: 'enabled', value: e.target.checked })} style={{ width: 'auto' }} />
                <span className="muted" style={{ fontSize: 12 }}>habilitado</span>
              </label>
            )}
            <span className="spacer" />
            {isAdmin && <button className="btn-icon" style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => test(w.id)}><Icon name="send" size={13} /> Testar</button>}
            {isAdmin && <button className="btn-icon" style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => remove.mutate(w.id)}><Icon name="trash" size={13} /> Remover</button>}
          </div>
          {testResult[w.id] && (
            <div className={testResult[w.id].ok ? '' : 'error'} style={{ fontSize: 12, marginTop: 6, color: testResult[w.id].ok ? 'var(--low)' : undefined }}>
              {testResult[w.id].msg}
            </div>
          )}
        </div>
      ))}
      {!list.data?.items.length && <div className="muted" style={{ fontSize: 12 }}>Nenhum canal cadastrado.</div>}

      {isAdmin && (
        <form className="row" style={{ marginTop: 14, alignItems: 'flex-end' }} onSubmit={(e) => { e.preventDefault(); if (name && url) create.mutate() }}>
          <div style={{ flex: '0 0 180px' }}>
            <label className="muted" style={{ fontSize: 11 }}>Nome do espaço</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: SOC-Alertas" />
          </div>
          <div style={{ flex: 1 }}>
            <label className="muted" style={{ fontSize: 11 }}>URL do webhook</label>
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://chat.googleapis.com/v1/spaces/…" />
          </div>
          <button className="primary btn-icon" type="submit" disabled={!name || !url || create.isPending}><Icon name="plus" size={15} /> Cadastrar</button>
        </form>
      )}
      {err && <div className="error" style={{ marginTop: 8 }}>{err}</div>}
    </Card>
  )
}
