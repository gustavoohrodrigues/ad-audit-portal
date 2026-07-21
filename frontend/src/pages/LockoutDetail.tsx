import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { fmtDate, eventLabel } from '@/lib/format'
import { Card, Loading } from '@/components/ui'
import { useAuth } from '@/hooks/useAuth'
import type { Lockout } from '@/types'

interface PlaybookStep { id: string; title: string; evidence: string }
interface LockoutDetailData {
  investigation: Lockout
  correlated_events: {
    id: number; event_id: number; type: string; time: string
    source_ip?: string; caller?: string; auth?: string; failure?: string
  }[]
  hypotheses: string[]
  playbook: PlaybookStep[]
  playbook_state: Record<string, { checked?: boolean; found?: boolean }>
}

const STATUSES = ['new', 'in_analysis', 'mitigated', 'false_positive', 'closed']

export function LockoutDetail() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const { can } = useAuth()
  const { data, isLoading } = useQuery({
    queryKey: ['lockout', id],
    queryFn: () => api.get<LockoutDetailData>(`/lockouts/${id}`),
  })

  const [note, setNote] = useState('')
  const [rootCause, setRootCause] = useState('')
  const [status, setStatus] = useState('')
  const [ticket, setTicket] = useState('')
  const [pb, setPb] = useState<Record<string, { checked?: boolean; found?: boolean }> | null>(null)

  const pbState = pb ?? data?.playbook_state ?? {}

  const saveNote = useMutation({
    mutationFn: () => api.post(`/lockouts/${id}/notes`, { note: note || '(playbook)', root_cause: rootCause || null, status: status || null, playbook_state: pbState }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lockout', id] }),
  })
  const linkTicket = useMutation({
    mutationFn: () => api.post(`/lockouts/${id}/link-ticket`, { ticket_number: ticket, system: 'glpi' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lockout', id] }),
  })

  if (isLoading || !data) return <Loading />
  const inv = data.investigation

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Bloqueio · {inv.target_username}</div>
          <div className="page-sub mono">{fmtDate(inv.lockout_time_utc)} · {inv.domain_controller}</div>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <Card title="Detalhes do bloqueio">
          <div className="row" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 6 }}>
            <Field label="Caller Computer" value={inv.caller_computer} />
            <Field label="IP de origem" value={inv.source_ip} />
            <Field label="Tipo de autenticação" value={inv.auth_type} />
            <Field label="Código de falha" value={inv.failure_code} />
            <Field label="Bloqueios do usuário (24h)" value={String(inv.lockouts_24h)} />
            <Field label="Bloqueios da mesma origem (24h)" value={String(inv.lockouts_same_source)} />
          </div>
        </Card>

        <Card title="Playbook guiado de investigação">
          {data.playbook.map((step) => {
            const st = pbState[step.id] || {}
            const set = (patch: { checked?: boolean; found?: boolean }) =>
              setPb({ ...pbState, [step.id]: { ...st, ...patch } })
            return (
              <div key={step.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                <label className="row" style={{ gap: 8, cursor: 'pointer' }}>
                  <input type="checkbox" checked={!!st.checked} onChange={(e) => set({ checked: e.target.checked })} style={{ width: 'auto' }} />
                  <strong style={{ textDecoration: st.checked ? 'line-through' : 'none', opacity: st.checked ? 0.6 : 1 }}>{step.title}</strong>
                  <span className="spacer" />
                  {can('note:write') && (
                    <button type="button" className={st.found ? 'primary' : ''} style={{ padding: '2px 8px', fontSize: 11 }} onClick={() => set({ found: !st.found })}>
                      {st.found ? '✓ Causa aqui' : 'Marcar causa'}
                    </button>
                  )}
                </label>
                <div className="muted" style={{ fontSize: 11, marginTop: 3, marginLeft: 24 }}>{step.evidence}</div>
              </div>
            )
          })}
          {can('note:write') && (
            <button style={{ marginTop: 10 }} disabled={saveNote.isPending} onClick={() => saveNote.mutate()}>
              {saveNote.isPending ? 'Salvando…' : 'Salvar progresso do playbook'}
            </button>
          )}
        </Card>
      </div>

      <Card title="Eventos correlacionados (4625 / 4771 / 4776)" className="table-wrap">
        <table>
          <thead><tr><th>Hora</th><th>Event ID</th><th>Tipo</th><th>Origem</th><th>IP</th><th>Auth</th><th>Falha</th></tr></thead>
          <tbody>
            {data.correlated_events.map((e) => (
              <tr key={e.id}>
                <td className="mono">{fmtDate(e.time)}</td>
                <td className="mono">{e.event_id}</td>
                <td>{eventLabel(e.type)}</td>
                <td className="mono">{e.caller || '—'}</td>
                <td className="mono">{e.source_ip || '—'}</td>
                <td>{e.auth || '—'}</td>
                <td className="mono muted">{e.failure || '—'}</td>
              </tr>
            ))}
            {!data.correlated_events.length && <tr><td colSpan={7} className="muted">Nenhuma falha correlacionada na janela.</td></tr>}
          </tbody>
        </table>
      </Card>

      {can('note:write') && (
        <Card title="Investigação">
          <div className="field">
            <label>Causa raiz</label>
            <input value={rootCause} onChange={(e) => setRootCause(e.target.value)} placeholder={inv.root_cause || 'Ex.: serviço com credencial antiga em SRV-APP-01'} />
          </div>
          <div className="field">
            <label>Observação do analista</label>
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={inv.analyst_note || 'Anotações…'} />
          </div>
          <div className="row">
            <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 200 }}>
              <option value="">Status ({inv.status})</option>
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <button className="primary" disabled={saveNote.isPending} onClick={() => saveNote.mutate()}>Salvar</button>
          </div>
          {can('ticket:link') && (
            <div className="row" style={{ marginTop: 14 }}>
              <input value={ticket} onChange={(e) => setTicket(e.target.value)} placeholder={inv.ticket_reference || 'Nº ticket GLPI'} style={{ width: 220 }} />
              <button disabled={!ticket || linkTicket.isPending} onClick={() => linkTicket.mutate()}>Vincular ticket</button>
              {inv.ticket_url && <a href={inv.ticket_url} target="_blank" rel="noreferrer">Abrir ticket {inv.ticket_reference}</a>}
            </div>
          )}
        </Card>
      )}
    </>
  )
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="row" style={{ borderBottom: '1px solid var(--border)', padding: '6px 0' }}>
      <span className="muted">{label}</span>
      <span className="spacer" />
      <span className="mono">{value || '—'}</span>
    </div>
  )
}
