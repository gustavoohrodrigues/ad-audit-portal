"""Schemas Pydantic de entrada/saída da API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.enums import (
    AlertStatus,
    InvestigationStatus,
    Severity,
)


# ---- Auth ----
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str = ""
    token_type: str = "bearer"
    expires_in: int = 0
    roles: list[str] = []
    mfa_required: bool = False
    mfa_token: Optional[str] = None
    mfa_enrollment_required: bool = False


class MfaLoginRequest(BaseModel):
    mfa_token: str
    code: str = Field(min_length=6, max_length=12)


class MfaEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_data_uri: str


class MfaStatusResponse(BaseModel):
    enabled: bool
    configured: bool


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None


class MeResponse(BaseModel):
    username: str
    roles: list[str]
    role: Optional[str]
    mfa_enabled: bool = False
    mfa_enrollment_required: bool = False


# ---- Eventos ----
class EventOut(BaseModel):
    id: int
    event_time_utc: datetime
    event_id: int
    event_type: str
    severity: Severity
    risk_score: int
    domain_controller: str
    target_username: Optional[str] = None
    target_upn: Optional[str] = None
    target_sid: Optional[str] = None
    actor_username: Optional[str] = None
    caller_computer: Optional[str] = None
    source_ip: Optional[str] = None
    failure_reason: Optional[str] = None
    is_privileged_target: bool
    is_critical_account: bool
    correlation_id: Optional[str] = None

    model_config = {"from_attributes": True}


class EventRawOut(EventOut):
    raw_event_json: dict[str, Any]


class PaginatedEvents(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[EventOut]


# ---- Usuário AD ----
class ADUserOut(BaseModel):
    sam_account_name: str
    user_principal_name: Optional[str] = None
    display_name: Optional[str] = None
    mail: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    manager: Optional[str] = None
    ou: Optional[str] = None
    is_disabled: bool = False
    is_locked: bool = False
    password_never_expires: bool = False
    password_not_required: bool = False
    is_privileged: bool = False
    is_critical: bool = False
    is_inactive: bool = False
    pwd_last_set: Optional[datetime] = None
    password_expires_at: Optional[datetime] = None
    last_logon_timestamp: Optional[datetime] = None
    when_created: Optional[datetime] = None
    when_changed: Optional[datetime] = None
    account_expires: Optional[datetime] = None
    lockout_time: Optional[datetime] = None
    member_of: list[str] = []
    risk_score: int = 0

    model_config = {"from_attributes": True}


# ---- Dashboard ----
class KpiCard(BaseModel):
    label: str
    value: int | float
    delta: Optional[float] = None
    severity: Optional[str] = None


class RankItem(BaseModel):
    label: str
    count: int
    extra: Optional[str] = None


class TimeBucket(BaseModel):
    ts: datetime
    count: int


class DashboardSummary(BaseModel):
    lockouts_24h: int
    lockouts_7d: int
    lockouts_30d: int
    failed_logons_24h: int
    password_events_24h: int
    admin_changes_24h: int
    privileged_group_changes_24h: int
    critical_alerts_open: int
    high_alerts_open: int
    medium_alerts_open: int
    inactive_accounts: int
    never_expire_accounts: int
    privileged_accounts: int
    events_ingested_24h: int
    ingestion_error_rate: float
    top_locked_users: list[RankItem]
    top_source_computers: list[RankItem]
    top_domain_controllers: list[RankItem]
    failed_logons_by_hour: list[TimeBucket]


# ---- Lockout / Investigação ----
class LockoutOut(BaseModel):
    id: int
    target_username: str
    target_sid: Optional[str] = None
    lockout_time_utc: datetime
    domain_controller: Optional[str] = None
    caller_computer: Optional[str] = None
    source_ip: Optional[str] = None
    auth_type: Optional[str] = None
    failure_code: Optional[str] = None
    lockouts_24h: int
    lockouts_same_source: int
    status: InvestigationStatus
    root_cause: Optional[str] = None
    analyst_note: Optional[str] = None
    ticket_reference: Optional[str] = None
    ticket_url: Optional[str] = None

    model_config = {"from_attributes": True}


class NoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=4000)
    root_cause: Optional[str] = None
    status: Optional[InvestigationStatus] = None
    playbook_state: Optional[dict[str, Any]] = None


class TicketLinkCreate(BaseModel):
    ticket_number: str = Field(min_length=1, max_length=64)
    ticket_url: Optional[str] = None
    system: str = "glpi"


# ---- Alertas ----
class AlertOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    severity: Severity
    risk_score: int
    status: AlertStatus
    target_username: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Relatórios ----
class ReportExportRequest(BaseModel):
    report_type: str = Field(examples=["lockouts", "events", "privileged_changes"])
    format: str = Field(default="csv", pattern="^(csv|json)$")
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    filters: dict[str, Any] = {}


# ---- Admin ----
class ConnectorTestRequest(BaseModel):
    connector_type: str


class ConnectorTestResult(BaseModel):
    ok: bool
    message: str


# ---- Notificações / ações ativas ----
class NotifyRequest(BaseModel):
    channel: str = Field(examples=["email", "teams", "slack", "discord", "winrm"])
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    target: Optional[str] = Field(default=None, description="e-mail, host WinRM, etc.")
    justification: str = Field(min_length=3, max_length=1000)
    ticket_reference: Optional[str] = None
    confirm: bool = Field(default=False, description="confirmação explícita da ação ativa")


# ---- Chat webhooks / central de mensagens ----
class ChatWebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=8, max_length=1000)
    provider: str = Field(default="google_chat")


class BroadcastRequest(BaseModel):
    channel: str = Field(pattern="^(email|google_chat)$")
    audience_filter: str = Field(examples=["password_expiring", "inactive", "privileged"])
    subject: str = Field(default="", max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    chat_webhook_id: Optional[int] = None
    justification: str = Field(min_length=3, max_length=1000)
    confirm: bool = False


# ---- Watchlists ----
class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = None


class WatchlistItemCreate(BaseModel):
    entity_type: str = Field(pattern="^(user|group|computer)$")
    entity_ref: str = Field(min_length=1, max_length=256)
    note: Optional[str] = None
