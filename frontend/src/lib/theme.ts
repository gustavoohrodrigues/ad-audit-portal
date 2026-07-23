// Sistema de temas — troca a identidade de cor da interface via data-theme.
// As cores reais vivem em CSS (styles/theme.css, blocos [data-theme="..."]).
export interface ThemeDef { id: string; label: string; accent: string; hint: string }

export const THEMES: ThemeDef[] = [
  { id: 'crimson', label: 'Crimson', accent: '#ff2d43', hint: 'Vermelho (padrão)' },
  { id: 'blue', label: 'Azul', accent: '#2f80ed', hint: 'Corporativo, calmo' },
  { id: 'emerald', label: 'Esmeralda', accent: '#10b981', hint: 'Verde, sóbrio' },
  { id: 'violet', label: 'Violeta', accent: '#8b5cf6', hint: 'Roxo, moderno' },
  { id: 'amber', label: 'Âmbar', accent: '#f59e0b', hint: 'Quente, alto contraste' },
]

const KEY = 'ad-theme'
export const THEME_EVENT = 'ad-themechange'

export function getTheme(): string {
  return localStorage.getItem(KEY) || 'crimson'
}

export function applyTheme(id: string): void {
  const theme = THEMES.find((t) => t.id === id) ? id : 'crimson'
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem(KEY, theme)
  window.dispatchEvent(new CustomEvent(THEME_EVENT, { detail: theme }))
}

// Aplica o tema salvo o quanto antes (chamado no bootstrap, antes do render).
export function initTheme(): void {
  document.documentElement.setAttribute('data-theme', getTheme())
}
