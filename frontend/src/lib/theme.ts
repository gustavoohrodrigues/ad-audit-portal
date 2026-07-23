// Sistema de temas — troca a identidade de cor da interface via data-theme.
// As cores reais vivem em CSS (styles/theme.css, blocos [data-theme="..."]).
export interface ThemeDef { id: string; label: string; accent: string; hint: string }

// Dois temas com referências (nomes = temas dos irmãos; descrições = citações).
export const THEMES: ThemeDef[] = [
  { id: 'crimson', label: 'Devils Never Cry', accent: '#ff2d43', hint: 'Vermelho carmesim — o caçador rebelde. “Jackpot!”' },
  { id: 'blue', label: 'Bury the Light', accent: '#2f80ed', hint: 'Azul cortante — poder frio e ambição. “I need more power.”' },
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
