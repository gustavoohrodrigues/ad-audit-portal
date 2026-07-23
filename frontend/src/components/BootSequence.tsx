import { useEffect, useRef, useState } from 'react'
import { BOOT_EVENT } from '@/lib/boot'

// Sequência de inicialização tech exibida após o login. Segue o tema (--accent).
const STEPS = [
  'Sessão AD estabelecida (LDAPS)',
  'Aplicando RBAC e políticas de acesso',
  'Carregando postura & Security Score',
  'Inicializando módulos de detecção',
  'Montando o Centro de Operações',
]

const STEP_MS = 360
const START_MS = 300

export function BootSequence() {
  const [active, setActive] = useState(false)
  const [closing, setClosing] = useState(false)
  const [step, setStep] = useState(0)
  const timers = useRef<number[]>([])

  useEffect(() => {
    const clear = () => { timers.current.forEach(clearTimeout); timers.current = [] }
    const start = () => {
      clear()
      setActive(true); setClosing(false); setStep(0)
      STEPS.forEach((_, i) => {
        timers.current.push(window.setTimeout(() => setStep(i + 1), START_MS + i * STEP_MS))
      })
      const total = START_MS + STEPS.length * STEP_MS + 420
      timers.current.push(window.setTimeout(() => setClosing(true), total))
      timers.current.push(window.setTimeout(() => { setActive(false); setClosing(false) }, total + 520))
    }
    window.addEventListener(BOOT_EVENT, start)
    return () => { window.removeEventListener(BOOT_EVENT, start); clear() }
  }, [])

  if (!active) return null
  const pct = Math.round((step / STEPS.length) * 100)

  return (
    <div className={`boot-overlay ${closing ? 'closing' : ''}`} role="status" aria-live="polite">
      <div className="boot-grid" />
      <div className="boot-scan" />
      <div className="boot-core">
        <div className="boot-logo">AD<span>·</span>AUDIT</div>
        <div className="boot-sub">Inicializando ambiente seguro</div>
        <div className="boot-ring" />
        <ul className="boot-steps">
          {STEPS.map((s, i) => (
            <li key={s} className={i < step ? 'done' : i === step ? 'active' : ''}>
              <span className="boot-tick">{i < step ? '✓' : i === step ? '▸' : '·'}</span>
              <span>{s}</span>
            </li>
          ))}
        </ul>
        <div className="boot-bar"><div className="boot-bar-fill" style={{ width: `${pct}%` }} /></div>
        <div className="boot-pct">{pct}% · carregando módulos</div>
      </div>
    </div>
  )
}
