import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Badge, Card, Loading } from '@/components/ui'
import { useAuth } from '@/hooks/useAuth'
import { ChatWebhooks } from '@/components/ChatWebhooks'

interface Integration {
  key: string; name: string; category: string; enabled: boolean
  endpoint: string; testable?: boolean; roadmap?: boolean
}

const CAT_LABEL: Record<string, string> = {
  core: 'Núcleo', alerta: 'Alertas', itsm: 'ITSM',
  observabilidade: 'Observabilidade', chatops: 'ChatOps',
}

export function Integrations() {
  const { can } = useAuth()
  const isAdmin = can('*') || can('investigation:manage')
  const { data, isLoading } = useQuery({
    queryKey: ['integrations'],
    queryFn: () => api.get<{ integrations: Integration[] }>('/admin/integrations'),
  })
  const [results, setResults] = useState<Record<string, { ok: boolean; message: string } | 'loading'>>({})

  async function test(key: string) {
    setResults((r) => ({ ...r, [key]: 'loading' }))
    try {
      const res = await api.post<{ ok: boolean; message: string }>(`/admin/integrations/${key}/test`)
      setResults((r) => ({ ...r, [key]: res }))
    } catch (e) {
      setResults((r) => ({ ...r, [key]: { ok: false, message: (e as Error).message } }))
    }
  }

  if (isLoading || !data) return <Loading />

  const groups = data.integrations.reduce<Record<string, Integration[]>>((acc, i) => {
    ;(acc[i.category] ||= []).push(i)
    return acc
  }, {})

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Central de Integrações</div>
          <div className="page-sub">Status e teste de conectividade · configuração via .env</div>
        </div>
      </div>

      {Object.entries(groups).map(([cat, items]) => (
        <div key={cat}>
          <div className="section-title">{CAT_LABEL[cat] || cat}</div>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
            {items.map((i) => {
              const res = results[i.key]
              return (
                <Card key={i.key}>
                  <div className="row">
                    <strong>{i.name}</strong>
                    <span className="spacer" />
                    {i.roadmap ? <Badge kind="info">roadmap</Badge>
                      : i.enabled ? <Badge kind="low">ativo</Badge>
                      : <Badge kind="medium">inativo</Badge>}
                  </div>
                  <div className="mono muted" style={{ fontSize: 11, margin: '8px 0', wordBreak: 'break-all' }}>
                    {i.endpoint || '— não configurado —'}
                  </div>
                  {i.testable && isAdmin && (
                    <button onClick={() => test(i.key)} disabled={res === 'loading'} style={{ width: '100%' }}>
                      {res === 'loading' ? 'Testando…' : 'Testar conexão'}
                    </button>
                  )}
                  {res && res !== 'loading' && (
                    <div className={res.ok ? '' : 'error'} style={{ marginTop: 8, fontSize: 12, color: res.ok ? 'var(--low)' : undefined }}>
                      {res.ok ? '✓ ' : '✗ '}{res.message}
                    </div>
                  )}
                </Card>
              )
            })}
          </div>
        </div>
      ))}

      <div style={{ marginTop: 18 }}>
        <ChatWebhooks />
      </div>

      {isAdmin && (
        <Card title="Sincronização do Active Directory" className="">
          <div className="row">
            <span className="muted">Resincroniza usuários, grupos e computadores a partir do AD.</span>
            <span className="spacer" />
            <SyncButton />
          </div>
        </Card>
      )}
    </>
  )
}

function SyncButton() {
  const [state, setState] = useState<'idle' | 'running' | string>('idle')
  async function run() {
    setState('running')
    try {
      const r = await api.post<{ users: { total: number }; groups: { total: number }; computers: { total: number } }>('/admin/sync/ad-users?scope=all')
      setState(`${r.users.total} usuários · ${r.groups.total} grupos · ${r.computers.total} computadores`)
    } catch (e) {
      setState('Falha: ' + (e as Error).message)
    }
  }
  return (
    <div className="row">
      {state !== 'idle' && state !== 'running' && <span className="muted" style={{ fontSize: 12 }}>{state}</span>}
      <button className="primary" onClick={run} disabled={state === 'running'}>
        {state === 'running' ? 'Sincronizando…' : 'Sincronizar agora'}
      </button>
    </div>
  )
}
