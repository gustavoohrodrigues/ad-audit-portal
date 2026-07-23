"""Modelo de MFA (TOTP) por usuário da aplicação (chaveado por sAMAccountName)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserMFA(SQLModel, table=True):
    __tablename__ = "user_mfa"

    id: Optional[int] = Field(default=None, primary_key=True)
    sam_account_name: str = Field(index=True, unique=True)
    secret: str
    enabled: bool = Field(default=False)
    confirmed_at: Optional[datetime] = None
    backup_codes: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class SecurityScan(SQLModel, table=True):
    """Varredura de rede (nmap) de um alvo autorizado. Ação ativa FORA do AD:
    exige RBAC + confirmação + auditoria e respeita a allowlist de alvos."""

    __tablename__ = "security_scans"
    __table_args__ = (Index("ix_scan_created", "created_at"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    target: str
    profile: str
    status: str = Field(default="pending")  # pending|running|done|error
    requested_by: Optional[str] = None
    hosts_up: int = Field(default=0)
    open_ports: int = Field(default=0)
    risk_count: int = Field(default=0)
    summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    result: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utcnow)
