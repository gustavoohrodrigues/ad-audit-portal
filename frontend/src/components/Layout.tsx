import { ReactNode, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { NotificationBell } from '@/components/NotificationBell'
import { CommandPalette } from '@/components/CommandPalette'
import { ShortcutsHelp } from '@/components/ShortcutsHelp'
import { Icon, IconName } from '@/components/icons'

interface NavItem { to: string; label: string; icon: IconName; cap: string; end?: boolean }
interface NavGroup { title: string; items: NavItem[] }

const NAV: NavGroup[] = [
  { title: 'Operação', items: [
    { to: '/', label: 'Dashboard', icon: 'dashboard', cap: 'dashboard:read', end: true },
    { to: '/health', label: 'Saúde', icon: 'health', cap: 'dashboard:read' },
    { to: '/lockouts', label: 'Bloqueios', icon: 'lock', cap: 'lockout:read' },
    { to: '/events', label: 'Eventos', icon: 'list', cap: 'user:read_basic' },
    { to: '/alerts', label: 'Alertas', icon: 'alert', cap: 'dashboard:read' },
  ] },
  { title: 'Segurança', items: [
    { to: '/posture', label: 'Postura', icon: 'posture', cap: 'dashboard:read' },
    { to: '/attack-surface', label: 'Superfície de Ataque', icon: 'target', cap: 'critical:read' },
  ] },
  { title: 'Inventário', items: [
    { to: '/search', label: 'Usuários', icon: 'users', cap: 'user:read_basic' },
    { to: '/groups', label: 'Grupos', icon: 'groups', cap: 'user:read_basic' },
    { to: '/computers', label: 'Computadores', icon: 'computer', cap: 'user:read_basic' },
    { to: '/watchlists', label: 'Watchlists', icon: 'star', cap: 'user:read_basic' },
  ] },
  { title: 'Comunicação', items: [
    { to: '/message-center', label: 'Central de Mensagens', icon: 'megaphone', cap: 'investigation:manage' },
    { to: '/notifications', label: 'Notificações', icon: 'mail', cap: 'dashboard:read' },
  ] },
  { title: 'Sistema', items: [
    { to: '/reports', label: 'Relatórios', icon: 'report', cap: 'report:export' },
    { to: '/integrations', label: 'Integrações', icon: 'integrations', cap: 'dashboard:read' },
    { to: '/collection-points', label: 'Pontos de Coleta', icon: 'capacity', cap: 'dashboard:read' },
    { to: '/capacity', label: 'Capacidade', icon: 'capacity', cap: 'critical:read' },
    { to: '/admin', label: 'Admin', icon: 'settings', cap: 'critical:read' },
  ] },
]

export function Layout({ children }: { children: ReactNode }) {
  const { me, logout, can } = useAuth()
  const nav = useNavigate()
  const [collapsed, setCollapsed] = useState<boolean>(() => localStorage.getItem('nav:collapsed') === '1')

  function toggle() {
    const v = !collapsed
    setCollapsed(v)
    localStorage.setItem('nav:collapsed', v ? '1' : '0')
  }
  const openSearch = () => window.dispatchEvent(new CustomEvent('open-command-palette'))

  return (
    <div className={`app-shell ${collapsed ? 'collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="sidebar-head">
          {!collapsed && (
            <div>
              <div className="brand">AD<span className="dot">·</span>AUDIT</div>
              <div className="brand-sub">NOC Identity Ops</div>
            </div>
          )}
          <button className="icon-btn" onClick={toggle} title={collapsed ? 'Expandir' : 'Recolher'} aria-label="Recolher menu">
            <Icon name={collapsed ? 'expand' : 'collapse'} size={18} />
          </button>
        </div>

        <button className="search-trigger" onClick={openSearch} title="Busca global (Ctrl+K)">
          <Icon name="search" size={16} />
          {!collapsed && <span>Buscar…</span>}
          {!collapsed && <kbd>Ctrl K</kbd>}
        </button>

        <nav className="nav">
          {NAV.map((group) => {
            const items = group.items.filter((n) => can(n.cap))
            if (!items.length) return null
            return (
              <div className="nav-group" key={group.title}>
                {!collapsed && <div className="nav-group-title">{group.title}</div>}
                {items.map((n) => (
                  <NavLink
                    key={n.to}
                    to={n.to}
                    end={n.end}
                    title={collapsed ? n.label : undefined}
                    className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                  >
                    <Icon name={n.icon} size={18} />
                    {!collapsed && <span className="nav-label">{n.label}</span>}
                  </NavLink>
                ))}
              </div>
            )
          })}
        </nav>

        <div className="nav-spacer" />

        <div className="sidebar-foot">
          <NotificationBell collapsed={collapsed} />
          <NavLink to="/account" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} title={collapsed ? 'Minha Conta' : undefined}>
            <Icon name="user" size={18} />
            {!collapsed && (
              <span className="nav-label" style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
                <span style={{ color: 'var(--text-0)' }}>{me?.username}</span>
                <span className="muted" style={{ fontSize: 11 }}>{me?.role}</span>
              </span>
            )}
          </NavLink>
          <button className="nav-item as-button" onClick={() => logout().then(() => nav('/login'))} title="Sair">
            <Icon name="logout" size={18} />
            {!collapsed && <span className="nav-label">Sair</span>}
          </button>
        </div>
      </aside>

      <main className="main">{children}</main>
      <CommandPalette />
      <ShortcutsHelp />
    </div>
  )
}
