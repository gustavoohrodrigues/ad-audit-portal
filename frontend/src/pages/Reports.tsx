import { useState } from 'react'
import { api } from '@/lib/api'
import { Card } from '@/components/ui'

const TYPES = [
  { key: 'lockouts', label: 'Bloqueios de conta' },
  { key: 'password_events', label: 'Eventos de senha' },
  { key: 'privileged_changes', label: 'Mudanças em grupos privilegiados' },
  { key: 'events', label: 'Todos os eventos' },
]

export function Reports() {
  const [type, setType] = useState('lockouts')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function exportCsv() {
    setBusy(true)
    setErr('')
    try {
      const blob = await api.download('/reports/export', { report_type: type, format: 'csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${type}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="topbar">
        <div>
          <div className="page-title">Relatórios</div>
          <div className="page-sub">Exportação CSV · ação auditada (RBAC: security_analyst/admin)</div>
        </div>
      </div>
      <Card title="Exportar relatório">
        <div className="row">
          <select value={type} onChange={(e) => setType(e.target.value)} style={{ width: 320 }}>
            {TYPES.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
          </select>
          <button className="primary" disabled={busy} onClick={exportCsv}>{busy ? 'Gerando…' : 'Exportar CSV'}</button>
        </div>
        {err && <div className="error">{err}</div>}
      </Card>
    </>
  )
}
