"""Modelos operacionais: fontes, alertas, regras de risco, investigações,
tickets, anotações, exportações, auditoria interna, retenção e checkpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import BigInteger, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel

from app.models.enums import (
    AlertStatus,
    InvestigationStatus,
    Severity,
    SourceStatus,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EventSource(SQLModel, table=True):
    """Fonte de eventos (WEF, WinRM, Elastic, Wazuh, Graylog, Splunk, API)."""

    __tablename__ = "event_sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    connector_type: str  # wef | winrm | elastic | wazuh | graylog | splunk | api
    endpoint: Optional[str] = None
    enabled: bool = Field(default=True)
    status: SourceStatus = Field(default=SourceStatus.unknown)
    last_event_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    events_ingested: int = Field(default=0)
    errors_count: int = Field(default=0)
    last_error: Optional[str] = None
    updated_at: datetime = Field(default_factory=_utcnow)


class CollectionCheckpoint(SQLModel, table=True):
    """Checkpoint por fonte de eventos (evita reprocessar / perder eventos)."""

    __tablename__ = "collection_checkpoints"
    __table_args__ = (
        Index("uq_checkpoint_source_channel", "source", "channel", unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    channel: str = Field(default="Security")
    # EventRecordID do Windows pode ser muito grande -> BIGINT
    last_event_record_id: Optional[int] = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    last_event_time_utc: Optional[datetime] = None
    bookmark: Optional[str] = None  # XML bookmark WEF/EventLog
    updated_at: datetime = Field(default_factory=_utcnow)


class RiskRule(SQLModel, table=True):
    __tablename__ = "risk_rules"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None
    event_type: Optional[str] = None
    base_score: int = Field(default=0)
    severity: Severity = Field(default=Severity.medium)
    enabled: bool = Field(default=True)
    conditions: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=_utcnow)


class Alert(SQLModel, table=True):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alert_status_time", "status", "created_at"),
        Index("ix_alert_dedup", "dedup_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    severity: Severity = Field(default=Severity.medium)
    risk_score: int = Field(default=0)
    status: AlertStatus = Field(default=AlertStatus.open)
    target_username: Optional[str] = None
    dedup_key: Optional[str] = Field(default=None, index=True)
    event_id: Optional[int] = Field(default=None, foreign_key="normalized_events.id")
    correlation_id: Optional[str] = None
    notified_channels: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    context: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    acknowledged_by: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class LockoutInvestigation(SQLModel, table=True):
    """Investigação de bloqueio (Event 4740) — somente leitura no AD."""

    __tablename__ = "lockout_investigations"
    __table_args__ = (
        Index("ix_lockinv_user_time", "target_username", "lockout_time_utc"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: Optional[int] = Field(default=None, foreign_key="normalized_events.id")
    target_username: str = Field(index=True)
    target_sid: Optional[str] = None
    lockout_time_utc: datetime
    domain_controller: Optional[str] = None
    caller_computer: Optional[str] = None
    source_ip: Optional[str] = None
    auth_type: Optional[str] = None  # Kerberos | NTLM
    failure_code: Optional[str] = None
    lockouts_24h: int = Field(default=0)
    lockouts_same_source: int = Field(default=0)
    correlated_event_ids: list[int] = Field(
        default_factory=list, sa_column=Column(JSONB)
    )
    status: InvestigationStatus = Field(default=InvestigationStatus.new)
    root_cause: Optional[str] = None
    analyst_note: Optional[str] = None
    playbook_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    ticket_reference: Optional[str] = None
    ticket_url: Optional[str] = None
    assigned_to: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class TicketLink(SQLModel, table=True):
    __tablename__ = "ticket_links"

    id: Optional[int] = Field(default=None, primary_key=True)
    system: str = Field(default="glpi")
    ticket_number: str
    ticket_url: Optional[str] = None
    entity: Optional[str] = None
    event_id: Optional[int] = Field(default=None, foreign_key="normalized_events.id")
    investigation_id: Optional[int] = Field(
        default=None, foreign_key="lockout_investigations.id"
    )
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


class AnalystNote(SQLModel, table=True):
    __tablename__ = "analyst_notes"

    id: Optional[int] = Field(default=None, primary_key=True)
    subject_type: str  # user | event | lockout | group
    subject_ref: str = Field(index=True)
    note: str
    author: str
    created_at: datetime = Field(default_factory=_utcnow)


class ReportExport(SQLModel, table=True):
    __tablename__ = "report_exports"

    id: Optional[int] = Field(default=None, primary_key=True)
    report_type: str
    format: str = Field(default="csv")  # csv | json | pdf
    requested_by: str
    parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    row_count: Optional[int] = None
    file_path: Optional[str] = None
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=_utcnow)


class InternalAuditLog(SQLModel, table=True):
    """Auditoria interna da aplicação (login, logout, acesso a JSON bruto, export…)."""

    __tablename__ = "internal_audit_log"
    __table_args__ = (
        Index("ix_audit_actor_time", "actor", "created_at"),
        Index("ix_audit_action_time", "action", "created_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    actor: str = Field(index=True)
    actor_role: Optional[str] = None
    action: str = Field(index=True)  # login|logout|login_failed|raw_access|export|search
    resource: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = Field(default=True)
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=_utcnow)


class ADSyncCheckpoint(SQLModel, table=True):
    """Watermark de sincronização incremental por fonte (uSNChanged)."""

    __tablename__ = "ad_sync_checkpoints"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True, unique=True)  # DC/base de bind
    highest_usn: int = Field(default=0)
    last_full_sync_at: Optional[datetime] = None
    last_incremental_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=_utcnow)


class RetentionPolicy(SQLModel, table=True):
    __tablename__ = "retention_policies"

    id: Optional[int] = Field(default=None, primary_key=True)
    data_type: str = Field(index=True, unique=True)  # events|raw_events|audit|alerts
    retention_days: int
    enabled: bool = Field(default=True)
    last_purge_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=_utcnow)
