import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { ParticleField } from '@/components/ParticleField'

const TAGLINES = [
  'Auditoria e postura de identidades em tempo real.',
  'Investigação de bloqueios com correlação e playbooks.',
  'Detecção de Kerberoasting, AS-REP e contas de risco.',
]

export function Login() {
  const { login, loginMfa, me } = useAuth()
  const nav = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [caps, setCaps] = useState(false)
  const [code, setCode] = useState('')
  const [mfaToken, setMfaToken] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [health, setHealth] = useState<'ok' | 'down' | 'checking'>('checking')

  useEffect(() => {
    fetch('/api/v1/health')
      .then((r) => setHealth(r.ok ? 'ok' : 'down'))
      .catch(() => setHealth('down'))
  }, [])

  if (me) nav('/', { replace: true })

  async function submitPassword(e: FormEvent) {
    e.preventDefault()
    setError(''); setBusy(true)
    try {
      const res = await login(username, password)
      if (res.mfaRequired && res.mfaToken) setMfaToken(res.mfaToken)
      else nav('/', { replace: true })
    } catch (err) {
      setError((err as Error).message || 'Falha na autenticação')
    } finally { setBusy(false) }
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault()
    setError(''); setBusy(true)
    try {
      await loginMfa(mfaToken!, code)
      nav('/', { replace: true })
    } catch (err) {
      setError((err as Error).message || 'Código inválido')
    } finally { setBusy(false) }
  }

  const healthMeta = {
    checking: { c: 'var(--text-2)', t: 'verificando serviço…' },
    ok: { c: 'var(--low)', t: 'serviço operacional' },
    down: { c: 'var(--critical)', t: 'serviço indisponível' },
  }[health]

  return (
    <div className="login-split">
      {/* HERO */}
      <div className="login-hero">
        <ParticleField />
        <div className="login-hero-top">
          <div className="login-logo">AD<span className="dot">·</span>AUDIT</div>
          <div className="brand-sub" style={{ marginTop: 4 }}>NOC · Crimson Ops</div>
        </div>
        <div className="login-tagline">
          <h2>Central de <span className="em">Operações</span><br />de Identidade do AD</h2>
          <div className="login-rotator">
            <div>
              {TAGLINES.map((t) => <span key={t}>{t}</span>)}
              <span>{TAGLINES[0]}</span>
            </div>
          </div>
        </div>
        <div className="login-caps">
          <div className="login-cap"><span className="ic">◈</span> Postura & Security Score</div>
          <div className="login-cap"><span className="ic">⚔</span> Superfície de ataque</div>
          <div className="login-cap"><span className="ic">🔒</span> Investigação de bloqueios</div>
          <div className="login-cap"><span className="ic">🛡</span> RBAC + MFA + Auditoria</div>
        </div>
      </div>

      {/* FORM */}
      <div className="login-form-side">
        <div className="glass-card">
          {!mfaToken ? (
            <form onSubmit={submitPassword}>
              <h1>Acessar o portal</h1>
              <div className="sub">Autenticação via Active Directory (LDAPS)</div>
              <div className="field">
                <label>Usuário</label>
                <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" placeholder="sAMAccountName" />
              </div>
              <div className="field">
                <label>Senha</label>
                <div className="pw-wrap">
                  <input
                    type={showPw ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyUp={(e) => setCaps(e.getModifierState && e.getModifierState('CapsLock'))}
                    autoComplete="current-password"
                    style={{ paddingRight: 54 }}
                  />
                  <button type="button" className="pw-toggle" onClick={() => setShowPw((s) => !s)} tabIndex={-1}>
                    {showPw ? 'ocultar' : 'mostrar'}
                  </button>
                </div>
                {caps && <div className="caps-hint">⚠ Caps Lock está ativado</div>}
              </div>
              {error && <div className="error">{error}</div>}
              <button className="primary" style={{ width: '100%', marginTop: 4 }} disabled={busy || !username || !password}>
                {busy ? 'Autenticando…' : 'Entrar →'}
              </button>
            </form>
          ) : (
            <form onSubmit={submitCode}>
              <h1>Verificação em duas etapas</h1>
              <div className="sub">Informe o código do seu app autenticador</div>
              <div className="field">
                <input
                  className="code-input"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                  inputMode="numeric" maxLength={8} autoFocus placeholder="000000"
                />
              </div>
              <div className="muted" style={{ fontSize: 11, marginBottom: 10 }}>
                Pode usar um código de backup se não tiver o app.
              </div>
              {error && <div className="error">{error}</div>}
              <button className="primary" style={{ width: '100%' }} disabled={busy || code.length < 6}>
                {busy ? 'Verificando…' : 'Verificar'}
              </button>
              <button type="button" style={{ width: '100%', marginTop: 8 }} onClick={() => { setMfaToken(null); setCode(''); setError('') }}>
                ← Voltar
              </button>
            </form>
          )}
          <div style={{ marginTop: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="login-health">
              <span className="status-dot" style={{ background: healthMeta.c, boxShadow: `0 0 6px ${healthMeta.c}` }} />
              {healthMeta.t}
            </span>
            <span className="muted" style={{ fontSize: 10 }}>v1.0</span>
          </div>
        </div>
      </div>
    </div>
  )
}
