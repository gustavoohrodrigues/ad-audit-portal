import { useEffect, useState } from 'react'
import { THEME_EVENT } from '@/lib/theme'

// Lê uma variável CSS do :root (ex.: '--accent') e reavalia ao trocar o tema.
// Usado pelos gráficos (Recharts), que precisam de uma cor concreta, não var().
function readVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

export function useThemeColors() {
  const [colors, setColors] = useState(() => ({
    accent: readVar('--accent', '#ff2d43'),
    accent2: readVar('--accent-2', '#ff5e6e'),
    accentDeep: readVar('--accent-deep', '#b00d22'),
    grid: readVar('--grid', 'rgba(255,90,110,0.08)'),
  }))
  useEffect(() => {
    const update = () => setColors({
      accent: readVar('--accent', '#ff2d43'),
      accent2: readVar('--accent-2', '#ff5e6e'),
      accentDeep: readVar('--accent-deep', '#b00d22'),
      grid: readVar('--grid', 'rgba(255,90,110,0.08)'),
    })
    window.addEventListener(THEME_EVENT, update)
    return () => window.removeEventListener(THEME_EVENT, update)
  }, [])
  return colors
}
