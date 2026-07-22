// Formatação de datas no fuso configurado (padrão America/Sao_Paulo).
const TZ = 'America/Sao_Paulo'

export function fmtDate(value?: string | null): string {
  if (!value) return '—'
  try {
    return new Intl.DateTimeFormat('pt-BR', {
      dateStyle: 'short',
      timeStyle: 'medium',
      timeZone: TZ,
    }).format(new Date(value))
  } catch {
    return value
  }
}

export function fmtTime(value?: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('pt-BR', {
    timeStyle: 'medium',
    timeZone: TZ,
  }).format(new Date(value))
}

export function fmtBytes(n?: number | null): string {
  if (!n || n <= 0) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(u.length - 1, Math.floor(Math.log(n) / Math.log(1024)))
  return `${(n / Math.pow(1024, i)).toFixed(i ? 1 : 0)} ${u[i]}`
}

export function relative(value?: string | null): string {
  if (!value) return '—'
  const diff = Date.now() - new Date(value).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'agora'
  if (min < 60) return `${min}m atrás`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h}h atrás`
  return `${Math.floor(h / 24)}d atrás`
}

export const EVENT_LABELS: Record<string, string> = {
  account_lockout: 'Bloqueio de conta',
  failed_logon: 'Falha de logon',
  successful_logon: 'Logon',
  password_change: 'Troca de senha (próprio)',
  password_reset: 'Reset de senha (operador)',
  account_changed: 'Alteração de conta',
  account_enabled: 'Conta habilitada',
  account_disabled: 'Conta desabilitada',
  user_created: 'Usuário criado',
  user_deleted: 'Usuário excluído',
  group_member_added: 'Membro adicionado a grupo',
  group_member_removed: 'Membro removido de grupo',
  account_renamed: 'Conta renomeada',
  account_unlocked: 'Conta desbloqueada',
  kerberos_preauth_failed: 'Falha pré-auth Kerberos',
  ntlm_validation: 'Validação NTLM',
  ds_object_modified: 'Objeto DS modificado',
  ds_object_created: 'Objeto DS criado',
  ds_object_deleted: 'Objeto DS excluído',
}

export function eventLabel(t: string): string {
  return EVENT_LABELS[t] || t
}
