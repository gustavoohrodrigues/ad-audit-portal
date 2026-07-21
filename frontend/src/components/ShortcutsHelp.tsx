import { useEffect, useState } from 'react'

const SHORTCUTS: { keys: string[]; desc: string }[] = [
  { keys: ['Ctrl', 'K'], desc: 'Busca global (usuários, grupos, computadores, páginas)' },
  { keys: ['?'], desc: 'Abrir/fechar esta ajuda de atalhos' },
  { keys: ['Esc'], desc: 'Fechar diálogos e sobreposições' },
  { keys: ['↑', '↓'], desc: 'Navegar resultados na busca global' },
  { keys: ['Enter'], desc: 'Abrir o item selecionado' },
]

function isTyping(el: EventTarget | null): boolean {
  const t = el as HTMLElement | null
  return !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)
}

export function ShortcutsHelp() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === '?' && !isTyping(e.target)) { e.preventDefault(); setOpen((o) => !o) }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (!open) return null

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setOpen(false)}>
      <div className="card" style={{ width: 460 }} onClick={(e) => e.stopPropagation()}>
        <div className="row" style={{ marginBottom: 14 }}>
          <strong style={{ fontSize: 16 }}>Atalhos de teclado</strong>
          <span className="spacer" />
          <button onClick={() => setOpen(false)} style={{ padding: '3px 10px' }}>✕</button>
        </div>
        {SHORTCUTS.map((s) => (
          <div key={s.desc} className="row" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontSize: 13 }}>{s.desc}</span>
            <span className="spacer" />
            <span className="row" style={{ gap: 4 }}>
              {s.keys.map((k) => (
                <kbd key={k} className="mono" style={{ background: 'var(--bg-3)', border: '1px solid var(--border-bright)', borderRadius: 5, padding: '2px 8px', fontSize: 12 }}>{k}</kbd>
              ))}
            </span>
          </div>
        ))}
        <div className="muted" style={{ fontSize: 11, marginTop: 12 }}>Pressione <span className="mono">?</span> a qualquer momento para abrir esta janela.</div>
      </div>
    </div>
  )
}
