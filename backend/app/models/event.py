"""Tabela central de eventos normalizados do Active Directory."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import BigInteger, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel

from app.models.enums import EventType, Severity


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NormalizedEvent(SQLModel, table=True):
    __tablename__ = "normalized_events"
    __table_args__ = (
        # Deduplicação: mesma tupla (DC, EventRecordID, EventID) = mesmo evento
        Index(
            "uq_event_dedup",
            "domain_controller",
            "event_record_id",
            "event_id",
            unique=True,
        ),
        Index("ix_event_target_time", "target_username", "event_time_utc"),
        Index("ix_event_sid_time", "target_sid", "event_time_utc"),
        Index("ix_event_type_time", "event_type", "event_time_utc"),
        Index("ix_event_dc_time", "domain_controller", "event_time_utc"),
        Index("ix_event_caller_time", "caller_computer", "event_time_utc"),
        Index("ix_event_upn", "target_upn"),
        Index("ix_event_correlation", "correlation_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    event_time_utc: datetime = Field(index=True)
    ingested_at: datetime = Field(default_factory=_utcnow)

    # EventRecordID do Windows pode ser muito grande (bilhões) -> BIGINT
    event_record_id: Optional[int] = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    event_id: int = Field(index=True)
    event_type: EventType = Field(default=EventType.other)
    severity: Severity = Field(default=Severity.info)
    risk_score: int = Field(default=0)

    domain: Optional[str] = None
    domain_controller: str = Field(default="unknown")

    target_username: Optional[str] = Field(default=None)
    target_upn: Optional[str] = None
    target_sid: Optional[str] = None
    target_dn: Optional[str] = None

    actor_username: Optional[str] = None
    actor_domain: Optional[str] = None
    actor_sid: Optional[str] = None

    caller_computer: Optional[str] = None
    source_host: Optional[str] = None
    source_ip: Optional[str] = None

    logon_id: Optional[str] = None
    workstation_name: Optional[str] = None
    authentication_package: Optional[str] = None
    status_code: Optional[str] = None
    failure_reason: Optional[str] = None

    collector_source: Optional[str] = None
    correlation_id: Optional[str] = Field(default=None)

    # Evento original preservado após normalização (JSONB para consulta).
    raw_event_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB)
    )

    is_privileged_target: bool = Field(default=False)
    is_critical_account: bool = Field(default=False)

    ticket_reference: Optional[str] = None
    analyst_note: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
