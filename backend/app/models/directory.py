"""Objetos sincronizados do AD (leitura): usuários, computadores, grupos, DCs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel

from app.models.enums import SourceStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ADUser(SQLModel, table=True):
    __tablename__ = "ad_users"
    __table_args__ = (
        Index("ix_aduser_sam", "sam_account_name"),
        Index("ix_aduser_upn", "user_principal_name"),
        Index("ix_aduser_sid", "object_sid", unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    object_sid: str = Field(index=True)
    object_guid: Optional[str] = None
    sam_account_name: str = Field(index=True)
    user_principal_name: Optional[str] = None
    display_name: Optional[str] = None
    given_name: Optional[str] = None
    surname: Optional[str] = None
    mail: Optional[str] = None
    employee_id: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    manager: Optional[str] = None
    distinguished_name: Optional[str] = None
    ou: Optional[str] = None

    member_of: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    user_account_control: Optional[int] = None
    admin_count: Optional[int] = None
    service_principal_name: list[str] = Field(
        default_factory=list, sa_column=Column(JSONB)
    )
    allowed_to_delegate_to: list[str] = Field(
        default_factory=list, sa_column=Column(JSONB)
    )
    sid_history: list[str] = Field(default_factory=list, sa_column=Column(JSONB))

    # Datas convertidas para UTC legível a partir dos atributos AD.
    when_created: Optional[datetime] = None
    when_changed: Optional[datetime] = None
    pwd_last_set: Optional[datetime] = None
    password_expires_at: Optional[datetime] = None
    last_logon_timestamp: Optional[datetime] = None
    account_expires: Optional[datetime] = None
    lockout_time: Optional[datetime] = None
    bad_pwd_count: Optional[int] = None
    bad_password_time: Optional[datetime] = None

    # Flags derivadas do userAccountControl para consulta rápida.
    is_disabled: bool = Field(default=False)
    is_locked: bool = Field(default=False)
    password_never_expires: bool = Field(default=False)
    password_not_required: bool = Field(default=False)
    dont_require_preauth: bool = Field(default=False)  # AS-REP roastable
    is_privileged: bool = Field(default=False)
    is_critical: bool = Field(default=False)
    is_inactive: bool = Field(default=False)
    risk_score: int = Field(default=0)

    synced_at: datetime = Field(default_factory=_utcnow)


class ADComputer(SQLModel, table=True):
    __tablename__ = "ad_computers"
    __table_args__ = (Index("ix_adcomputer_name", "sam_account_name"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    object_sid: str = Field(index=True)
    object_guid: Optional[str] = None
    sam_account_name: str
    dns_host_name: Optional[str] = None
    distinguished_name: Optional[str] = None
    operating_system: Optional[str] = None
    when_created: Optional[datetime] = None
    last_logon_timestamp: Optional[datetime] = None
    user_account_control: Optional[int] = None
    is_disabled: bool = Field(default=False)
    synced_at: datetime = Field(default_factory=_utcnow)


class ADGroup(SQLModel, table=True):
    __tablename__ = "ad_groups"
    __table_args__ = (Index("ix_adgroup_name", "sam_account_name"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    object_sid: str = Field(index=True)
    object_guid: Optional[str] = None
    sam_account_name: str
    display_name: Optional[str] = None
    distinguished_name: Optional[str] = None
    description: Optional[str] = None
    members: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    member_count: int = Field(default=0)
    is_privileged: bool = Field(default=False)
    admin_count: Optional[int] = None
    synced_at: datetime = Field(default_factory=_utcnow)


class DomainController(SQLModel, table=True):
    __tablename__ = "domain_controllers"

    id: Optional[int] = Field(default=None, primary_key=True)
    hostname: str = Field(index=True, unique=True)
    domain: Optional[str] = None
    ip_address: Optional[str] = None
    status: SourceStatus = Field(default=SourceStatus.unknown)
    last_event_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    event_count_24h: int = Field(default=0)
    ingestion_lag_seconds: Optional[int] = None
    updated_at: datetime = Field(default_factory=_utcnow)
