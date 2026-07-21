import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { fmtDate } from '@/lib/format'
import { eventLabel } from '@/lib/format'
import { Badge, Card, Loading, SeverityBadge } from '@/components/ui'
import { NotifyModal } from '@/components/NotifyModal'
import { Icon } from '@/components/icons'
import { useAuth } from '@/hooks/useAuth'
import type { ADUser, EventRow } from '@/types'

function Fact({ label, value }: { label: string; value?: string | null }) {
  return (
    <div style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
      <div className="muted" style={{ fontSize: 11 }}>{label}</div>
      <div>{value || '—'}</div>
    </div>
  )
}

/** Badge do estado de expiração de senha. */
function PasswordExpiry({ user }: { user: ADUser }) {
  if (user.password_never_expires) return <Badge kind="info">Senha nunca expira</Badge>
  if (!user.password_expires_at) return null
  const days = Math.ceil((new Date(user.password_expires_at).getTime() - Date.now()) / 86400000)
  if (days < 0) return <Badge kind="critical">Senha expirada há {Math.abs(days)}d</Badge>
  if (days <= 7) return <Badge kind="high">Senha expira em {days}d ⚠</Badge>
  if (days <= 14) return <Badge kind="medium">Senha expira em {days}d</Badge>
  return <Badge kind="low">Senha expira em {days}d</Badge>
}

interface LockoutOrigin {
  username: string
  powershell_command: string
  collected: { time: string; origin?: string; domain_controller?: string; source_ip?: string }[]
  live: { time: string; origin?: string; domain_controller?: string }[]
  live_error?: string
  hint: string
}

function LockoutOriginPanel({ identifier }: { identifier: string }) {
  const [copied, setCopied] = useState(false)
  const [live, setLive] = useState(false)
  const { data, isFetching } = useQuery({
    queryKey: ['lockout-origin', identifier, live],
    queryFn: () => api.get<LockoutOrigin>(`/users/${encodeURIComponent(identifier)}/lockout-origin${live ? '?live=true' : ''}`),
  })
  if (!data) return null
  const rows = [...data.collected, ...data.live]

  return (
    <Card title="Origem do bloqueio (Event 4740)">
      <div className="row" style={{ marginBottom: 10 }}>
        <span className="muted" style={{ fontSize: 12 }}>
          {live ? 'Consulta ao vivo nos Domain Controllers (WinRM).' : 'Origens já coletadas.'}
        </span>
        <span className="spacer" />
        <button className={`btn-icon ${live ? 'primary' : ''}`} disabled={isFetching} onClick={() => setLive(true)} style={{ padding: '4px 10px', fontSize: 12 }}>
          <Icon name="zap" size={14} /> {isFetching && live ? 'Consultando DCs…' : 'Consultar ao vivo (WinRM)'}
        </button>
      </div>
      {data.live_error && <div className="error" style={{ fontSize: 12, marginBottom: 8 }}>WinRM: {data.live_error}</div>}
      {rows.length > 0 ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Data/Hora</th><th>Origem do bloqueio</th><th>DC</th><th>IP</th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td className="mono">{fmtDate(r.time)}</td>
                  <td className="mono" style={{ color: 'var(--accent-2)' }}>{r.origin || '—'}</td>
                  <td className="mono muted">{r.domain_controller || '—'}</td>
                  <td className="mono muted">{(r as { source_ip?: string }).source_ip || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="muted" style={{ fontSize: 13, marginBottom: 10 }}>
          Nenhuma origem coletada ainda. Rode o comando abaixo em um Domain Controller
          para descobrir de qual máquina veio o bloqueio (Properties[1]):
        </div>
      )}
      <div style={{ marginTop: 12 }}>
        <div className="row" style={{ marginBottom: 4 }}>
          <span className="muted" style={{ fontSize: 11 }}>Comando PowerShell</span>
          <span className="spacer" />
          <button
            className="btn-icon"
            style={{ padding: '3px 10px', fontSize: 11 }}
            onClick={() => { navigator.clipboard.writeText(data.powershell_command); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
          >
            <Icon name={copied ? 'check' : 'copy'} size={13} /> {copied ? 'Copiado' : 'Copiar'}
          </button>
        </div>
        <pre className="mono" style={{ background: 'var(--bg-0)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {data.powershell_command}
        </pre>
      </div>
    </Card>
  )
}

export function UserDetail() {
  const { identifier = '' } = useParams()
  const { can } = useAuth()
  const [notifyOpen, setNotifyOpen] = useState(false)
  const id = encodeURIComponent(identifier)

  const user = useQuery({ queryKey: ['user', identifier], queryFn: () => api.get<ADUser>(`/users/${id}`) })
  const timeline = useQuery({ queryKey: ['user-tl', identifier], queryFn: () => api.get<EventRow[]>(`/users/${id}/timeline`) })
  const risk = useQuery({ queryKey: ['user-risk', identifier], queryFn: () => api.get<{ risk_score: number; reasons: string[] }>(`/users/${id}/risk`) })

  if (user.isLoading) return <Loading />
  if (user.isError || !user.data) return <Card><div className="error">Usuário não encontrado.</div></Card>
  const u = user.data

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">{u.display_name || u.sam_account_name}</div>
          <div className="page-sub mono">{u.user_principal_name || u.sam_account_name}</div>
        </div>
        <div className="row">
          <div className="chips">
            {u.is_locked ? <Badge kind="critical">Bloqueado</Badge> : u.is_disabled ? <Badge kind="medium">Desabilitado</Badge> : <Badge kind="low">Ativo</Badge>}
            {u.is_privileged && <Badge kind="priv">Privilegiado</Badge>}
            {u.is_critical && <Badge kind="crit-acct">Crítico</Badge>}
          </div>
          {can('investigation:manage') && (
            <button className="primary btn-icon" onClick={() => setNotifyOpen(true)}>
              <Icon name="send" size={15} /> Avisar usuário
            </button>
          )}
        </div>
      </div>
      {notifyOpen && <NotifyModal identifier={u.sam_account_name} onClose={() => setNotifyOpen(false)} />}

      <div className="grid" style={{ gridTemplateColumns: '340px 1fr' }}>
        <div>
          <Card title="Identidade">
            <Fact label="Login" value={u.sam_account_name} />
            <Fact label="E-mail" value={u.mail} />
            <Fact label="Departamento" value={u.department} />
            <Fact label="Cargo" value={u.title} />
            <Fact label="Gestor" value={u.manager} />
            <Fact label="OU" value={u.ou} />
          </Card>
          <Card title="Estado da conta" className="">
            <Fact label="Última troca de senha" value={fmtDate(u.pwd_last_set)} />
            <Fact label="Último logon" value={fmtDate(u.last_logon_timestamp)} />
            <Fact label="Criada em" value={fmtDate(u.when_created)} />
            <Fact label="Última alteração" value={fmtDate(u.when_changed)} />
            <Fact label="Expiração da conta" value={fmtDate(u.account_expires)} />
            <div className="chips" style={{ marginTop: 10 }}>
              <PasswordExpiry user={u} />
              {u.password_not_required && <Badge kind="high">Password Not Required</Badge>}
              {u.is_inactive && <Badge kind="info">Inativo</Badge>}
            </div>
          </Card>
          {risk.data && (
            <Card title={`Risco: ${risk.data.risk_score}/100`}>
              <div className="chips">{risk.data.reasons.map((r) => <Badge key={r} kind="medium">{r}</Badge>)}</div>
              {!risk.data.reasons.length && <div className="muted">Sem fatores de risco.</div>}
            </Card>
          )}
        </div>

        <Card title="Timeline de eventos">
          {timeline.isLoading && <Loading />}
          <div className="timeline">
            {(timeline.data || []).map((e) => (
              <div key={e.id} className={`tl-item ${e.severity}`}>
                <div className="tl-time">{fmtDate(e.event_time_utc)} · {e.domain_controller}</div>
                <div className="row">
                  <strong>{eventLabel(e.event_type)}</strong>
                  <SeverityBadge severity={e.severity} />
                  {e.caller_computer && <span className="mono muted">origem: {e.caller_computer}</span>}
                  {e.actor_username && <span className="muted">por {e.actor_username}</span>}
                </div>
              </div>
            ))}
            {!timeline.data?.length && !timeline.isLoading && <div className="muted">Sem eventos registrados.</div>}
          </div>
        </Card>
      </div>

      <div style={{ marginTop: 16 }}>
        <LockoutOriginPanel identifier={u.sam_account_name} />
      </div>
    </>
  )
}
