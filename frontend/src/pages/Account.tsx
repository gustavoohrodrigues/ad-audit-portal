import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Badge, Card, Loading } from '@/components/ui'
import { useAuth } from '@/hooks/useAuth'

interface MfaStatus { enabled: boolean; configured: boolean }
interface MfaSetup { secret: string; otpauth_uri: string; qr_data_uri: string }

export function Account() {
  const { me, refresh } = useAuth()
  const qc = useQueryClient()
  const status = useQuery({ queryKey: ['mfa-status'], queryFn: () => api.get<MfaStatus>('/auth/mfa/status') })
  const [setup, setSetup] = useState<MfaSetup | null>(null)
  const [code, setCode] = useState('')
  const [backup, setBackup] = useState<string[] | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function startSetup() {
    setError(''); setBusy(true)
    try {
      setSetup(await api.post<MfaSetup>('/auth/mfa/setup'))
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  async function enable() {
    setError(''); setBusy(true)
    try {
      const r = await api.post<{ backup_codes: string[] }>('/auth/mfa/enable', { code })
      setBackup(r.backup_codes)
      setSetup(null); setCode('')
      qc.invalidateQueries({ queryKey: ['mfa-status'] })
      await refresh()  // atualiza me.mfa_enrollment_required (libera o guard)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  async function disable() {
    if (!confirm('Desativar o MFA da sua conta?')) return
    await api.post('/auth/mfa/disable')
    setBackup(null)
    qc.invalidateQueries({ queryKey: ['mfa-status'] })
  }

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Minha Conta</div>
          <div className="page-sub mono">{me?.username} · {me?.role}</div>
        </div>
      </div>

      {me?.mfa_enrollment_required && (
        <div className="card" style={{ borderColor: 'var(--medium)', background: 'rgba(255,176,32,0.1)', marginBottom: 14 }}>
          <strong style={{ color: 'var(--medium)' }}>MFA obrigatório para o seu perfil</strong>
          <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
            Configure a autenticação em duas etapas abaixo para liberar o acesso ao portal.
          </div>
        </div>
      )}

      <Card title="Autenticação em duas etapas (MFA)" className="">
        {status.isLoading && <Loading />}
        {status.data && (
          <>
            <div className="row" style={{ marginBottom: 14 }}>
              <span>Status:</span>
              {status.data.enabled
                ? <Badge kind="low">Ativo</Badge>
                : <Badge kind="medium">Inativo</Badge>}
            </div>

            {status.data.enabled && !backup && (
              <button onClick={disable}>Desativar MFA</button>
            )}

            {!status.data.enabled && !setup && !backup && (
              <>
                <p className="muted" style={{ marginBottom: 12, fontSize: 13 }}>
                  Proteja seu acesso exigindo um código do app autenticador (Google
                  Authenticator, Microsoft Authenticator, etc.) além da senha.
                </p>
                <button className="primary" onClick={startSetup} disabled={busy}>
                  {busy ? 'Gerando…' : 'Configurar MFA'}
                </button>
              </>
            )}

            {setup && (
              <div className="grid" style={{ gridTemplateColumns: '220px 1fr', alignItems: 'center' }}>
                <img src={setup.qr_data_uri} alt="QR Code MFA" style={{ width: 200, borderRadius: 8, background: '#fff', padding: 8 }} />
                <div>
                  <p style={{ marginBottom: 8, fontSize: 13 }}>
                    1. Escaneie o QR Code no seu app autenticador.<br />
                    2. Digite o código gerado para ativar.
                  </p>
                  <div className="muted mono" style={{ fontSize: 11, marginBottom: 10, wordBreak: 'break-all' }}>
                    Chave manual: {setup.secret}
                  </div>
                  <div className="field" style={{ maxWidth: 220 }}>
                    <input
                      value={code}
                      onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                      maxLength={6} placeholder="000000" inputMode="numeric"
                      style={{ fontSize: 20, letterSpacing: 5, textAlign: 'center', fontFamily: 'var(--mono)' }}
                    />
                  </div>
                  {error && <div className="error">{error}</div>}
                  <button className="primary" onClick={enable} disabled={busy || code.length < 6}>Ativar MFA</button>
                  <button style={{ marginLeft: 8 }} onClick={() => { setSetup(null); setError('') }}>Cancelar</button>
                </div>
              </div>
            )}

            {backup && (
              <div>
                <div className="row" style={{ marginBottom: 8 }}>
                  <Badge kind="low">MFA ativado!</Badge>
                </div>
                <p className="muted" style={{ fontSize: 13, marginBottom: 10 }}>
                  Guarde estes <strong>códigos de backup</strong> em local seguro. Cada um funciona uma única vez, caso você perca o app.
                </p>
                <div className="chips" style={{ gap: 10 }}>
                  {backup.map((c) => <span key={c} className="mono" style={{ padding: '6px 12px', background: 'var(--bg-3)', borderRadius: 6, fontSize: 15 }}>{c}</span>)}
                </div>
                <button style={{ marginTop: 14 }} onClick={() => setBackup(null)}>Concluir</button>
              </div>
            )}
            {error && !setup && <div className="error">{error}</div>}
          </>
        )}
      </Card>
    </>
  )
}
