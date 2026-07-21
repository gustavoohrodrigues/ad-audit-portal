import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { api } from '@/lib/api'
import type { Me, Role } from '@/types'

interface AuthCtx {
  me: Me | null
  loading: boolean
  login: (u: string, p: string) => Promise<{ mfaRequired: boolean; mfaToken?: string }>
  loginMfa: (token: string, code: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  can: (cap: string) => boolean
}

const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx)

// Capacidades por role (espelha o RBAC do backend para habilitar UI).
const CAPS: Record<Role, string[]> = {
  viewer: ['dashboard:read', 'user:read_basic'],
  helpdesk: ['dashboard:read', 'user:read_basic', 'lockout:read', 'password_event:read', 'note:write', 'ticket:link'],
  security_analyst: ['dashboard:read', 'user:read_basic', 'user:read_full', 'lockout:read', 'password_event:read', 'note:write', 'ticket:link', 'event:raw_read', 'report:export', 'investigation:manage', 'critical:read'],
  administrator: ['*'],
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .get<Me>('/auth/me')
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setLoading(false))
  }, [])

  const refresh = async () => {
    const m = await api.get<Me>('/auth/me')
    setMe(m)
  }

  const login = async (username: string, password: string) => {
    const res = await api.login(username, password)
    if (res.mfa_required && res.mfa_token) {
      return { mfaRequired: true, mfaToken: res.mfa_token }
    }
    await refresh()
    return { mfaRequired: false }
  }

  const loginMfa = async (token: string, code: string) => {
    await api.loginMfa(token, code)
    await refresh()
  }

  const logout = async () => {
    await api.logout().catch(() => {})
    setMe(null)
  }

  const can = (cap: string) => {
    if (!me) return false
    return me.roles.some((r) => {
      const caps = CAPS[r] || []
      return caps.includes('*') || caps.includes(cap)
    })
  }

  return <Ctx.Provider value={{ me, loading, login, loginMfa, logout, refresh, can }}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
