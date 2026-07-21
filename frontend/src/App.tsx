import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { Layout } from '@/components/Layout'
import { Loading } from '@/components/ui'
import { Login } from '@/pages/Login'
import { Dashboard } from '@/pages/Dashboard'
import { UserSearch } from '@/pages/UserSearch'
import { UserDetail } from '@/pages/UserDetail'
import { Lockouts } from '@/pages/Lockouts'
import { LockoutDetail } from '@/pages/LockoutDetail'
import { Events } from '@/pages/Events'
import { Alerts } from '@/pages/Alerts'
import { Reports } from '@/pages/Reports'
import { Admin } from '@/pages/Admin'
import { SecurityPosture } from '@/pages/SecurityPosture'
import { Groups } from '@/pages/Groups'
import { Computers } from '@/pages/Computers'
import { Integrations } from '@/pages/Integrations'
import { Health } from '@/pages/Health'
import { Account } from '@/pages/Account'
import { AttackSurface } from '@/pages/AttackSurface'
import { Notifications } from '@/pages/Notifications'
import { Watchlists } from '@/pages/Watchlists'
import { Capacity } from '@/pages/Capacity'
import { MessageCenter } from '@/pages/MessageCenter'
import { ReactNode } from 'react'

function Protected({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Loading />
  if (!me) return <Navigate to="/login" replace />
  // MFA obrigatório por perfil e ainda não configurado -> força a página de conta
  if (me.mfa_enrollment_required && location.pathname !== '/account') {
    return <Navigate to="/account" replace />
  }
  return <Layout>{children}</Layout>
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/health" element={<Protected><Health /></Protected>} />
      <Route path="/posture" element={<Protected><SecurityPosture /></Protected>} />
      <Route path="/attack-surface" element={<Protected><AttackSurface /></Protected>} />
      <Route path="/notifications" element={<Protected><Notifications /></Protected>} />
      <Route path="/message-center" element={<Protected><MessageCenter /></Protected>} />
      <Route path="/watchlists" element={<Protected><Watchlists /></Protected>} />
      <Route path="/groups" element={<Protected><Groups /></Protected>} />
      <Route path="/computers" element={<Protected><Computers /></Protected>} />
      <Route path="/integrations" element={<Protected><Integrations /></Protected>} />
      <Route path="/account" element={<Protected><Account /></Protected>} />
      <Route path="/search" element={<Protected><UserSearch /></Protected>} />
      <Route path="/users/:identifier" element={<Protected><UserDetail /></Protected>} />
      <Route path="/lockouts" element={<Protected><Lockouts /></Protected>} />
      <Route path="/lockouts/:id" element={<Protected><LockoutDetail /></Protected>} />
      <Route path="/events" element={<Protected><Events /></Protected>} />
      <Route path="/alerts" element={<Protected><Alerts /></Protected>} />
      <Route path="/reports" element={<Protected><Reports /></Protected>} />
      <Route path="/admin" element={<Protected><Admin /></Protected>} />
      <Route path="/capacity" element={<Protected><Capacity /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
