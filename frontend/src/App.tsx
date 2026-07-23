import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { lazy, Suspense, ReactNode } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { Layout } from '@/components/Layout'
import { Loading } from '@/components/ui'
import { BootSequence } from '@/components/BootSequence'
import { Login } from '@/pages/Login'

// Rotas carregadas sob demanda (code-splitting): reduz o JS inicial e adia o
// carregamento de páginas pesadas (Recharts) até serem realmente acessadas.
// O Dashboard também é lazy para que a tela de login não baixe os gráficos.
const Dashboard = lazy(() => import('@/pages/Dashboard').then(m => ({ default: m.Dashboard })))
const UserSearch = lazy(() => import('@/pages/UserSearch').then(m => ({ default: m.UserSearch })))
const UserDetail = lazy(() => import('@/pages/UserDetail').then(m => ({ default: m.UserDetail })))
const Lockouts = lazy(() => import('@/pages/Lockouts').then(m => ({ default: m.Lockouts })))
const LockoutDetail = lazy(() => import('@/pages/LockoutDetail').then(m => ({ default: m.LockoutDetail })))
const Events = lazy(() => import('@/pages/Events').then(m => ({ default: m.Events })))
const Alerts = lazy(() => import('@/pages/Alerts').then(m => ({ default: m.Alerts })))
const Reports = lazy(() => import('@/pages/Reports').then(m => ({ default: m.Reports })))
const Admin = lazy(() => import('@/pages/Admin').then(m => ({ default: m.Admin })))
const SecurityPosture = lazy(() => import('@/pages/SecurityPosture').then(m => ({ default: m.SecurityPosture })))
const Groups = lazy(() => import('@/pages/Groups').then(m => ({ default: m.Groups })))
const Computers = lazy(() => import('@/pages/Computers').then(m => ({ default: m.Computers })))
const Integrations = lazy(() => import('@/pages/Integrations').then(m => ({ default: m.Integrations })))
const Health = lazy(() => import('@/pages/Health').then(m => ({ default: m.Health })))
const Account = lazy(() => import('@/pages/Account').then(m => ({ default: m.Account })))
const AttackSurface = lazy(() => import('@/pages/AttackSurface').then(m => ({ default: m.AttackSurface })))
const Notifications = lazy(() => import('@/pages/Notifications').then(m => ({ default: m.Notifications })))
const Watchlists = lazy(() => import('@/pages/Watchlists').then(m => ({ default: m.Watchlists })))
const Capacity = lazy(() => import('@/pages/Capacity').then(m => ({ default: m.Capacity })))
const MessageCenter = lazy(() => import('@/pages/MessageCenter').then(m => ({ default: m.MessageCenter })))
const CollectionPoints = lazy(() => import('@/pages/CollectionPoints').then(m => ({ default: m.CollectionPoints })))
const SecurityScan = lazy(() => import('@/pages/SecurityScan').then(m => ({ default: m.SecurityScan })))

function Protected({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Loading />
  if (!me) return <Navigate to="/login" replace />
  // MFA obrigatório por perfil e ainda não configurado -> força a página de conta
  if (me.mfa_enrollment_required && location.pathname !== '/account') {
    return <Navigate to="/account" replace />
  }
  return <Layout><Suspense fallback={<Loading />}>{children}</Suspense></Layout>
}

export function App() {
  return (
    <>
    <BootSequence />
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
      <Route path="/collection-points" element={<Protected><CollectionPoints /></Protected>} />
      <Route path="/security-scan" element={<Protected><SecurityScan /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </>
  )
}
