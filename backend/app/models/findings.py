"""Camada normalizada de achados de segurança (findings).

Modelo único para todos os scanners/coletores (Trivy, Lynis, coletor Linux,
parsers de contêiner, import normalizado genérico, etc.). Deduplicação por
fingerprint estável e correlação entre fontes. NÃO escreve no AD.

Severidade/estados são strings validadas na camada de serviço (evita a
complexidade de ALTER TYPE de ENUM nativo e facilita filtros/dedup).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FindingIngestion(SQLModel, table=True):
    """Linhagem de ingestão: cada import/scan gera um lote rastreável."""

    __tablename__ = "finding_ingestions"

    id: Optional[int] = Field(default=None, primary_key=True)
    ingestion_id: str = Field(index=True, unique=True)
    source_tool: str
    source_format: str
    asset_name: Optional[str] = None
    environment: str = Field(default="unknown")
    total: int = Field(default=0)
    created: int = Field(default=0)
    updated: int = Field(default=0)
    status: str = Field(default="ok")  # ok | partial | error
    error: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


class SecurityFinding(SQLModel, table=True):
    __tablename__ = "security_findings"
    __table_args__ = (
        Index("ix_finding_fp", "fingerprint"),
        Index("ix_finding_sev_status", "severity", "status"),
        Index("ix_finding_asset", "asset_type", "asset_name"),
        Index("ix_finding_cat", "category"),
        Index("ix_finding_lastseen", "last_seen"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    fingerprint: str = Field(index=True)
    ingestion_id: Optional[str] = Field(default=None, index=True)

    # origem
    source_tool: str = Field(default="manual")
    source_type: Optional[str] = None       # image | filesystem | dependency | secret | config | host
    category: str = Field(default="vulnerability")
    subcategory: Optional[str] = None

    # ativo
    asset_type: str = Field(default="host")  # image | host | repo | container | service | dependency
    asset_id: Optional[str] = None
    asset_name: str = Field(default="unknown")
    environment: str = Field(default="unknown")
    host_name: Optional[str] = None
    service_name: Optional[str] = None

    # conteúdo
    severity: str = Field(default="unknown")   # critical|high|medium|low|info|unknown
    confidence: str = Field(default="medium")  # high|medium|low
    title: str = Field(default="")
    description: Optional[str] = None
    evidence: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    remediation: Optional[str] = None
    references: list[str] = Field(default_factory=list, sa_column=Column(JSONB))

    # identificadores técnicos
    cve: Optional[str] = None
    cwe: Optional[str] = None
    cvss: Optional[float] = None
    package_name: Optional[str] = None
    installed_version: Optional[str] = None
    fixed_version: Optional[str] = None
    file_path: Optional[str] = None
    config_path: Optional[str] = None

    # contexto de risco
    exploit_available: bool = Field(default=False)
    internet_exposed: bool = Field(default=False)
    privileged_context: bool = Field(default=False)
    risk_score: int = Field(default=0)
    risk_band: str = Field(default="low")

    # ciclo de vida
    occurrences: int = Field(default=1)
    status: str = Field(default="open")           # open | suppressed | resolved
    remediation_state: str = Field(default="none")  # none | in_progress | fixed | wont_fix
    assignee: Optional[str] = None
    suppressed_until: Optional[datetime] = None
    suppression_reason: Optional[str] = None
    suppressed_by: Optional[str] = None

    tags: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    correlation_id: Optional[str] = None

    first_seen: datetime = Field(default_factory=_utcnow)
    last_seen: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
