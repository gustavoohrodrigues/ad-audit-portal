import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'

interface Hit { label: string; sub?: string; path: string; privileged?: boolean }
interface SearchResult { users: Hit[]; groups: Hit[]; computers: Hit[]; pages: Hit[] }

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [res, setRes] = useState<SearchResult | null>(null)
  const [active, setActive] = useState(0)
  const nav = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)

  // atalho Ctrl+K / ⌘K
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((o) => !o)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 30)
    else { setQ(''); setRes(null); setActive(0) }
  }, [open])

  useEffect(() => {
    if (!q.trim()) { setRes(null); return }
    const t = setTimeout(async () => {
      try { setRes(await api.get<SearchResult>(`/search?q=${encodeURIComponent(q.trim())}`)) }
      catch { setRes(null) }
    }, 180)
    return () => clearTimeout(t)
  }, [q])

  const flat = useMemo(() => {
    if (!res) return [] as { group: string; hit: Hit }[]
    return [
      ...res.pages.map((h) => ({ group: 'Páginas', hit: h })),
      ...res.users.map((h) => ({ group: 'Usuários', hit: h })),
      ...res.groups.map((h) => ({ group: 'Grupos', hit: h })),
      ...res.computers.map((h) => ({ group: 'Computadores', hit: h })),
    ]
  }, [res])

  function go(hit: Hit) { setOpen(false); nav(hit.path) }

  function onInputKey(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, flat.length - 1)) }
    if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
    if (e.key === 'Enter' && flat[active]) { e.preventDefault(); go(flat[active].hit) }
  }

  if (!open) return null

  let idx = -1
  let lastGroup = ''

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 200, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: '12vh' }} onClick={() => setOpen(false)}>
      <div className="card" style={{ width: 560, maxHeight: '70vh', overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: 0 }} onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => { setQ(e.target.value); setActive(0) }}
          onKeyDown={onInputKey}
          placeholder="Buscar usuários, grupos, computadores, páginas…"
          style={{ border: 'none', borderBottom: '1px solid var(--border)', borderRadius: 0, fontSize: 15, padding: 16 }}
        />
        <div style={{ overflow: 'auto' }}>
          {flat.map(({ group, hit }) => {
            idx++
            const showGroup = group !== lastGroup
            lastGroup = group
            const isActive = idx === active
            const myIdx = idx
            return (
              <div key={`${group}-${hit.path}-${hit.label}`}>
                {showGroup && <div className="muted" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, padding: '8px 14px 2px' }}>{group}</div>}
                <div
                  onMouseEnter={() => setActive(myIdx)}
                  onClick={() => go(hit)}
                  style={{ padding: '9px 14px', cursor: 'pointer', background: isActive ? 'var(--bg-3)' : 'transparent', display: 'flex', gap: 10, alignItems: 'center' }}
                >
                  <span className="mono">{hit.label}</span>
                  {hit.privileged && <span className="badge priv">priv</span>}
                  {hit.sub && <span className="muted" style={{ fontSize: 12 }}>{hit.sub}</span>}
                </div>
              </div>
            )
          })}
          {q && !flat.length && <div className="muted" style={{ padding: 20, textAlign: 'center' }}>Nada encontrado.</div>}
          {!q && <div className="muted" style={{ padding: 20, textAlign: 'center', fontSize: 12 }}>Digite para buscar · <span className="mono">Esc</span> para fechar</div>}
        </div>
      </div>
    </div>
  )
}
