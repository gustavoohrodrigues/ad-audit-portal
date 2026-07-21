import { useState } from 'react'
import { api } from '@/lib/api'
import { Badge } from '@/components/ui'

const CHANNELS = [
  { key: 'email', label: 'E-mail' },
  { key: 'teams', label: 'Teams' },
  { key: 'slack', label: 'Slack' },
  { key: 'discord', label: 'Discord' },
  { key: 'winrm', label: 'Mensagem Windows (msg)' },
]

const TEMPLATES: Record<string, { subject: string; message: string }> = {
  senha_expirar: {
    subject: 'Sua senha está prestes a expirar',
    message: 'Olá, sua senha de rede expira em breve. Por favor, troque-a o quanto antes.',
  },
  bloqueio: {
    subject: 'Detectamos bloqueios na sua conta',
    message: 'Sua conta apresentou bloqueios recentes. Verifique dispositivos com credenciais antigas (celular, VPN, unidades mapeadas).',
  },
  livre: { subject: '', message: '' },
}

export function NotifyModal({ identifier, onClose }: { identifier: string; onClose: () => void }) {
  const [channel, setChannel] = useState('email')
  const [target, setTarget] = useState('')
  const [tpl, setTpl] = useState('senha_expirar')
  const [subject, setSubject] = useState(TEMPLATES.senha_expirar.subject)
  const [message, setMessage] = useState(TEMPLATES.senha_expirar.message)
  const [justification, setJustification] = useState('')
  const [ticket, setTicket] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null)

  function applyTemplate(key: string) {
    setTpl(key)
    setSubject(TEMPLATES[key].subject)
    setMessage(TEMPLATES[key].message)
  }

  async function send() {
    setBusy(true); setResult(null)
    try {
      const r = await api.post<{ correlation_id: string }>(`/users/${encodeURIComponent(identifier)}/notify`, {
        channel, target: target || undefined, subject, message, justification,
        ticket_reference: ticket || undefined, confirm,
      })
      setResult({ ok: true, msg: `Enviado (id ${r.correlation_id.slice(0, 8)})` })
    } catch (e) {
      setResult({ ok: false, msg: (e as Error).message })
    } finally { setBusy(false) }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={onClose}>
      <div className="card" style={{ width: 520, maxHeight: '90vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
        <div className="row" style={{ marginBottom: 12 }}>
          <strong style={{ fontSize: 16 }}>Avisar usuário — {identifier}</strong>
          <span className="spacer" />
          <button onClick={onClose} style={{ padding: '3px 10px' }}>✕</button>
        </div>
        <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
          Ação ativa (fora do AD) — auditada. Não altera o Active Directory.
        </div>

        <div className="field">
          <label>Canal</label>
          <select value={channel} onChange={(e) => setChannel(e.target.value)}>
            {CHANNELS.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
        </div>
        {(channel === 'email' || channel === 'winrm') && (
          <div className="field">
            <label>{channel === 'winrm' ? 'Host de destino (allowlist)' : 'E-mail (opcional)'}</label>
            <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder={channel === 'winrm' ? 'host.empresa.local' : 'usuario@empresa.local'} />
          </div>
        )}
        <div className="field">
          <label>Modelo</label>
          <div className="row">
            <button type="button" className={tpl === 'senha_expirar' ? 'primary' : ''} onClick={() => applyTemplate('senha_expirar')} style={{ padding: '4px 8px', fontSize: 11 }}>Senha a expirar</button>
            <button type="button" className={tpl === 'bloqueio' ? 'primary' : ''} onClick={() => applyTemplate('bloqueio')} style={{ padding: '4px 8px', fontSize: 11 }}>Bloqueio</button>
            <button type="button" className={tpl === 'livre' ? 'primary' : ''} onClick={() => applyTemplate('livre')} style={{ padding: '4px 8px', fontSize: 11 }}>Livre</button>
          </div>
        </div>
        <div className="field">
          <label>Assunto</label>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} />
        </div>
        <div className="field">
          <label>Mensagem</label>
          <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={3} style={{ width: '100%', background: 'var(--bg-1)', border: '1px solid var(--border)', color: 'var(--text-0)', borderRadius: 8, padding: 10, fontFamily: 'inherit' }} />
        </div>
        <div className="field">
          <label>Justificativa (obrigatória)</label>
          <input value={justification} onChange={(e) => setJustification(e.target.value)} placeholder="Motivo desta notificação" />
        </div>
        <div className="field">
          <label>Ticket relacionado (opcional)</label>
          <input value={ticket} onChange={(e) => setTicket(e.target.value)} placeholder="Nº GLPI" />
        </div>
        <label className="row" style={{ gap: 8, marginBottom: 12 }}>
          <input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} style={{ width: 'auto' }} />
          <span>Confirmo o envio desta ação ativa</span>
        </label>
        {result && <div className={result.ok ? '' : 'error'} style={{ marginBottom: 10, color: result.ok ? 'var(--low)' : undefined }}>{result.ok ? '✓ ' : '✗ '}{result.msg}</div>}
        <button className="primary" onClick={send} disabled={busy || !confirm || justification.length < 3 || !subject || !message} style={{ width: '100%' }}>
          {busy ? 'Enviando…' : 'Enviar notificação'}
        </button>
        {channel !== 'email' && <div className="muted" style={{ fontSize: 11, marginTop: 8 }}><Badge kind="medium">nota</Badge> O canal precisa estar configurado no .env para o envio funcionar.</div>}
      </div>
    </div>
  )
}
