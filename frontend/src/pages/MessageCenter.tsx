import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Card, Loading } from '@/components/ui'

interface Filter { key: string; label: string }
interface Audience {
  filter: string; label: string; email_domain: string; count: number
  items: { sam_account_name: string; display_name?: string; email: string; password_expires_at?: string }[]
}
interface ChatWebhook { id: number; name: string; provider: string; url_masked: string; enabled: boolean }

export function MessageCenter() {
  const [filter, setFilter] = useState('password_expiring')
  const [channel, setChannel] = useState<'email' | 'google_chat'>('email')
  const [webhookId, setWebhookId] = useState<number | ''>('')
  const [message, setMessage] = useState('')
  const [subject, setSubject] = useState('')
  const [justification, setJustification] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null)

  const filters = useQuery({ queryKey: ['msg-filters'], queryFn: () => api.get<{ filters: Filter[]; email_domain: string }>('/messaging/filters') })
  const audience = useQuery({
    queryKey: ['msg-audience', filter],
    queryFn: () => api.get<Audience>(`/messaging/audience?filter=${filter}&limit=2000`),
  })
  const webhooks = useQuery({ queryKey: ['chat-webhooks'], queryFn: () => api.get<{ items: ChatWebhook[] }>('/chat-webhooks') })

  async function send() {
    setBusy(true); setResult(null)
    try {
      const r = await api.post<{ recipients: number; sent: number; failed: number }>('/messaging/broadcast', {
        channel, audience_filter: filter, subject, message,
        chat_webhook_id: channel === 'google_chat' ? webhookId || null : null,
        justification, confirm,
      })
      setResult({ ok: r.failed === 0, text: `${r.sent} enviado(s), ${r.failed} falha(s) de ${r.recipients} destinatário(s)` })
    } catch (e) {
      setResult({ ok: false, text: (e as Error).message })
    } finally { setBusy(false) }
  }

  const canSend = confirm && message.length > 0 && justification.length >= 3 &&
    (channel === 'email' || (channel === 'google_chat' && webhookId !== '')) &&
    (audience.data?.count || 0) > 0

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Central de Mensagens</div>
          <div className="page-sub">Filtre um público e envie uma notificação (e-mail ou Google Chat) · auditado</div>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
        {/* Composição */}
        <Card title="Mensagem">
          <div className="field">
            <label>Público-alvo</label>
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              {(filters.data?.filters || []).map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Canal</label>
            <select value={channel} onChange={(e) => setChannel(e.target.value as 'email' | 'google_chat')}>
              <option value="email">E-mail (para cada conta · @{filters.data?.email_domain || 'astra-sa.com'})</option>
              <option value="google_chat">Google Chat (webhook)</option>
            </select>
          </div>
          {channel === 'google_chat' && (
            <div className="field">
              <label>Espaço (webhook)</label>
              <select value={webhookId} onChange={(e) => setWebhookId(e.target.value ? Number(e.target.value) : '')}>
                <option value="">Selecione um espaço…</option>
                {(webhooks.data?.items || []).filter((w) => w.enabled).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </select>
              {!webhooks.data?.items.length && <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Nenhum webhook cadastrado. Cadastre em Integrações → Google Chat.</div>}
            </div>
          )}
          <div className="field">
            <label>Assunto (opcional)</label>
            <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Ex.: Sua senha está prestes a expirar" />
          </div>
          <div className="field">
            <label>Mensagem</label>
            <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={5}
              placeholder="Escreva aqui a mensagem que será enviada…"
              style={{ width: '100%', background: 'var(--bg-1)', border: '1px solid var(--border)', color: 'var(--text-0)', borderRadius: 8, padding: 10, fontFamily: 'inherit' }} />
          </div>
          <div className="field">
            <label>Justificativa (obrigatória)</label>
            <input value={justification} onChange={(e) => setJustification(e.target.value)} placeholder="Motivo do envio" />
          </div>
          <label className="row" style={{ gap: 8, marginBottom: 12 }}>
            <input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} style={{ width: 'auto' }} />
            <span>Confirmo o envio para {audience.data?.count ?? 0} destinatário(s)</span>
          </label>
          {result && <div className={result.ok ? '' : 'error'} style={{ marginBottom: 10, color: result.ok ? 'var(--low)' : undefined }}>{result.ok ? '✓ ' : '✗ '}{result.text}</div>}
          <button className="primary" style={{ width: '100%' }} disabled={busy || !canSend} onClick={send}>
            {busy ? 'Enviando…' : `Enviar para ${audience.data?.count ?? 0} conta(s)`}
          </button>
        </Card>

        {/* Prévia do público */}
        <Card title={audience.data ? `Público: ${audience.data.label} (${audience.data.count})` : 'Público'} className="table-wrap">
          {audience.isLoading && <Loading />}
          {audience.data && (
            <table>
              <thead><tr><th>Conta</th><th>E-mail</th><th>Expira</th></tr></thead>
              <tbody>
                {audience.data.items.slice(0, 200).map((i) => (
                  <tr key={i.sam_account_name}>
                    <td className="mono">{i.sam_account_name}</td>
                    <td className="mono muted">{i.email}</td>
                    <td className="mono muted">{i.password_expires_at?.slice(0, 10) || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {audience.data && audience.data.count > 200 && <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>Exibindo 200 de {audience.data.count}. O envio abrange todos.</div>}
        </Card>
      </div>
    </>
  )
}
