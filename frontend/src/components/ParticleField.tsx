import { useEffect, useRef } from 'react'
import { THEME_EVENT } from '@/lib/theme'

// Lê uma CSS var e converte hex -> "r, g, b" para uso em rgba() no canvas.
function cssVar(name: string, fb: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fb
}
function hexToRgb(hex: string): string {
  const m = hex.replace('#', '')
  const v = m.length === 3 ? m.split('').map((x) => x + x).join('') : m
  const n = parseInt(v, 16)
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`
}

/**
 * Rede de partículas (constellation) em canvas — segue a cor do tema atual.
 * Leve, sem dependências, respeita prefers-reduced-motion.
 */
export function ParticleField() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const cv = canvasRef.current
    if (!cv) return
    const ctx = cv.getContext('2d')
    if (!ctx) return
    const parent = cv.parentElement
    if (!parent) return

    const c: CanvasRenderingContext2D = ctx
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let width = 0
    let height = 0
    let raf = 0

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = parent!.clientWidth
      height = parent!.clientHeight
      cv!.width = width * dpr
      cv!.height = height * dpr
      cv!.style.width = `${width}px`
      cv!.style.height = `${height}px`
      c.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()
    window.addEventListener('resize', resize)

    const count = Math.min(70, Math.max(24, Math.floor((width * height) / 16000)))
    const nodes = Array.from({ length: count }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      r: Math.random() * 1.8 + 0.6,
    }))
    const mouse = { x: -999, y: -999 }
    const onMove = (e: MouseEvent) => {
      const rect = cv!.getBoundingClientRect()
      mouse.x = e.clientX - rect.left
      mouse.y = e.clientY - rect.top
    }
    const onLeave = () => { mouse.x = -999; mouse.y = -999 }
    parent.addEventListener('mousemove', onMove)
    parent.addEventListener('mouseleave', onLeave)

    const LINK = 130

    // Cores derivadas do tema (reavaliadas ao trocar de tema).
    let linkRgb = hexToRgb(cssVar('--accent', '#ff2d43'))
    let dotRgb = hexToRgb(cssVar('--accent-2', '#ff5e6e'))
    const onTheme = () => {
      linkRgb = hexToRgb(cssVar('--accent', '#ff2d43'))
      dotRgb = hexToRgb(cssVar('--accent-2', '#ff5e6e'))
    }
    window.addEventListener(THEME_EVENT, onTheme)

    function draw() {
      c.clearRect(0, 0, width, height)
      for (const n of nodes) {
        n.x += n.vx
        n.y += n.vy
        if (n.x < 0 || n.x > width) n.vx *= -1
        if (n.y < 0 || n.y > height) n.vy *= -1
        const dmx = mouse.x - n.x
        const dmy = mouse.y - n.y
        const dm = Math.hypot(dmx, dmy)
        if (dm < 160) { n.x += (dmx * 0.0009 * (160 - dm)) / 160; n.y += (dmy * 0.0009 * (160 - dm)) / 160 }
      }
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i]
          const b = nodes[j]
          const d = Math.hypot(a.x - b.x, a.y - b.y)
          if (d < LINK) {
            c.strokeStyle = `rgba(${linkRgb}, ${(1 - d / LINK) * 0.5})`
            c.lineWidth = 1
            c.beginPath()
            c.moveTo(a.x, a.y)
            c.lineTo(b.x, b.y)
            c.stroke()
          }
        }
      }
      for (const n of nodes) {
        c.fillStyle = `rgba(${dotRgb}, 0.85)`
        c.beginPath()
        c.arc(n.x, n.y, n.r, 0, Math.PI * 2)
        c.fill()
      }
      if (!reduced) raf = requestAnimationFrame(draw)
    }
    draw()

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      window.removeEventListener(THEME_EVENT, onTheme)
      parent.removeEventListener('mousemove', onMove)
      parent.removeEventListener('mouseleave', onLeave)
    }
  }, [])

  return <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} />
}
