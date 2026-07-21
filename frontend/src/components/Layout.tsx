import { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { NotificationBell } from '@/components/NotificationBell'
import { CommandPalette } from '@/components/CommandPalette'
import { ShortcutsHelp } from '@/components/ShortcutsHelp'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '▚', cap: 'dashboard:read' },
  { to: '/health', label: 'Saúde', icon: '❤', cap: 'dashboard:read' },
  { to: '/posture', label: 'Postura', icon: '◈', cap: 'dashboard:read' },
  { to: '/attack-surface', label: 'Superfície de Ataque', icon: '⚔', cap: 'critical:read' },
  { to: '/search', label: 'Usuários', icon: '◍', cap: 'user:read_basic' },
  { to: '/groups', label: 'Grupos', icon: '⧉', cap: 'user:read_basic' },
  { to: '/computers', label: 'Computadores', icon: '▦', cap: 'user:read_basic' },
  { to: '/watchlists', label: 'Watchlists', icon: '★', cap: 'user:read_basic' },
  { to: '/lockouts', label: 'Bloqueios', icon: '🔒', cap: 'lockout:read' },
  { to: '/events', label: 'Eventos', icon: '≣', cap: 'user:read_basic' },
  { to: '/alerts', label: 'Alertas', icon: '⚠', cap: 'dashboard:read' },
  { to: '/message-center', label: 'Central de Mensagens', icon: '📣', cap: 'investigation:manage' },
  { to: '/notifications', label: 'Notificações', icon: '✉', cap: 'dashboard:read' },
  { to: '/reports', label: 'Relatórios', icon: '⬇', cap: 'report:export' },
  { to: '/integrations', label: 'Integrações', icon: '⇄', cap: 'dashboard:read' },
  { to: '/capacity', label: 'Capacidade', icon: '▤', cap: 'critical:read' },
  { to: '/admin', label: 'Admin', icon: '⚙', cap: 'critical:read' },
]

export function Layout({ children }: { children: ReactNode }) {
  const { me, logout, can } = useAuth()
  const nav = useNavigate()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">AD<span className="dot">·</span>AUDIT</div>
        <div className="brand-sub">NOC Identity Ops</div>
        <div className="muted" style={{ fontSize: 10, marginBottom: 10 }}>Busca global: <span className="mono">Ctrl+K</span></div>
        <nav>
          {NAV.filter((n) => can(n.cap)).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <span aria-hidden>{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="nav-spacer" />
        <div style={{ marginBottom: 12 }}>
          <NotificationBell />
        </div>
        <div style={{ fontSize: 12 }}>
          <div style={{ color: 'var(--text-0)' }}>{me?.username}</div>
          <div className="muted">{me?.role}</div>
          <NavLink to="/account" className="nav-item" style={{ marginTop: 8, padding: '7px 10px' }}>
            <span aria-hidden>👤</span> Minha Conta
          </NavLink>
          <button style={{ marginTop: 6, width: '100%' }} onClick={() => logout().then(() => nav('/login'))}>
            Sair
          </button>
        </div>
      </aside>
      <main className="main">{children}</main>
      <CommandPalette />
      <ShortcutsHelp />
    </div>
  )
}
