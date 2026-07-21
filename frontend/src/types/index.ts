export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical'
export type Role = 'viewer' | 'helpdesk' | 'security_analyst' | 'administrator'

export interface Me {
  username: string
  roles: Role[]
  role: Role | null
  mfa_enabled?: boolean
  mfa_enrollment_required?: boolean
}

export interface RankItem { label: string; count: number; extra?: string }
export interface TimeBucket { ts: string; count: number }

export interface DashboardSummary {
  lockouts_24h: number
  lockouts_7d: number
  lockouts_30d: number
  failed_logons_24h: number
  password_events_24h: number
  admin_changes_24h: number
  privileged_group_changes_24h: number
  critical_alerts_open: number
  high_alerts_open: number
  medium_alerts_open: number
  inactive_accounts: number
  never_expire_accounts: number
  privileged_accounts: number
  events_ingested_24h: number
  ingestion_error_rate: number
  top_locked_users: RankItem[]
  top_source_computers: RankItem[]
  top_domain_controllers: RankItem[]
  failed_logons_by_hour: TimeBucket[]
}

export interface ADUser {
  sam_account_name: string
  user_principal_name?: string
  display_name?: string
  mail?: string
  department?: string
  title?: string
  manager?: string
  ou?: string
  is_disabled: boolean
  is_locked: boolean
  password_never_expires: boolean
  password_not_required: boolean
  is_privileged: boolean
  is_critical: boolean
  is_inactive: boolean
  pwd_last_set?: string
  password_expires_at?: string
  last_logon_timestamp?: string
  when_created?: string
  when_changed?: string
  account_expires?: string
  lockout_time?: string
  member_of: string[]
  risk_score: number
}

export interface EventRow {
  id: number
  event_time_utc: string
  event_id: number
  event_type: string
  severity: Severity
  risk_score: number
  domain_controller: string
  target_username?: string
  target_upn?: string
  actor_username?: string
  caller_computer?: string
  source_ip?: string
  failure_reason?: string
  is_privileged_target: boolean
  is_critical_account: boolean
  correlation_id?: string
}

export interface Lockout {
  id: number
  target_username: string
  lockout_time_utc: string
  domain_controller?: string
  caller_computer?: string
  source_ip?: string
  auth_type?: string
  failure_code?: string
  lockouts_24h: number
  lockouts_same_source: number
  status: string
  root_cause?: string
  analyst_note?: string
  ticket_reference?: string
  ticket_url?: string
}

export interface Alert {
  id: number
  title: string
  description?: string
  severity: Severity
  risk_score: number
  status: string
  target_username?: string
  created_at: string
}

export interface SecurityScore {
  score: number
  grade: string
  computed_from: {
    users: number
    computers: number
    privileged: number
    spn_accounts: number
    legacy_machines: number
  }
  factors: { label: string; count: number; impact: number; severity: string }[]
}

export interface InventoryCategory {
  key: string
  label: string
  count: number
  severity: string
}

export interface HealthCheck {
  id: string
  severity: 'error' | 'warning' | 'ok'
  summary: string
  detail: string
  count: number
  link?: string
  muted: boolean
}

export interface HealthStatus {
  status: 'HEALTH_OK' | 'HEALTH_WARN' | 'HEALTH_ERR'
  summary: { error: number; warning: number; muted: number }
  checks: HealthCheck[]
  evaluated_at: string
}

export interface NotificationSummary {
  status: 'HEALTH_OK' | 'HEALTH_WARN' | 'HEALTH_ERR'
  count: number
  error: number
  warning: number
  items: { kind: string; id: string; severity: string; title: string; link?: string }[]
}

export interface DetectionItem {
  sam_account_name: string
  display_name?: string
  is_privileged: boolean
  admin_count?: number
  password_never_expires: boolean
  pwd_last_set?: string
  last_logon_timestamp?: string
  spn: string[]
  risk_score: number
  reasons: string[]
}

export interface DetectionResult {
  technique: string
  recommendation: string
  count: number
  items: DetectionItem[]
}

export interface ScorePoint { date: string; score: number; grade: string }

export interface NotificationRow {
  time: string
  channel: string
  target?: string
  subject?: string
  status: string
  error?: string
  requested_by?: string
  role?: string
  ticket?: string
  correlation_id: string
}

export interface DomainControllerHealth {
  hostname: string
  status: 'healthy' | 'degraded' | 'down' | 'unknown'
  last_event_at?: string
  event_count_24h: number
  ingestion_lag_seconds?: number
}
