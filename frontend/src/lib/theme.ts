// Sistema de temas — troca a identidade de cor da interface via data-theme.
// As cores reais vivem em CSS (styles/theme.css, blocos [data-theme="..."]).
export interface ThemeDef { id: string; label: string; accent: string; hint: string }

// Dois temas, referência a Devil May Cry: Dante (vermelho) e Vergil (azul).
export const THEMES: ThemeDef[] = [
  { id: 'crimson', label: 'Dante', accent: '#ff2d43', hint: 'Vermelho rebelde — “Jackpot!” (Devil May Cry)' },
  { id: 'blue', label: 'Vergil', accent: '#2f80ed', hint: 'Azul frio e cortante — “I need more power.” (Devil May Cry)' },
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
