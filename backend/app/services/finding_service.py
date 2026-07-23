"""Persistência de findings: ingestão com deduplicação, supressão e agregações.

Deduplica por fingerprint estável (re-scan atualiza o mesmo registro em vez de
duplicar). Preserva supressões vigentes ao reingestar. Somente leitura no AD.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.findings import FindingIngestion, SecurityFinding

logger = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def ingest_findings(
    session: AsyncSession, canonical: list[dict[str, Any]], *,
    source_tool: str, source_format: str, environment: str,
    asset_name: str | None, created_by: str | None,
) -> dict[str, Any]:
    ingestion_id = uuid.uuid4().hex
    now = _now()
    created = updated = 0

    for f in canonical:
        fp = f["fingerprint"]
        existing = (await session.execute(
            select(SecurityFinding).where(SecurityFinding.fingerprint == fp)
        )).scalars().first()
        f["environment"] = f.get("environment") or environment
        if existing:
            existing.last_seen = now
            existing.occurrences = (existing.occurrences or 1) + 1
            existing.severity = f["severity"]
            existing.risk_score = f["risk_score"]
            existing.risk_band = f["risk_band"]
            existing.fixed_version = f.get("fixed_version")
            existing.cvss = f.get("cvss")
            existing.ingestion_id = ingestion_id
            existing.updated_at = now
            # se a supressão expirou, reabre
            if existing.status == "suppressed" and existing.suppressed_until \
                    and _aware(existing.suppressed_until) <= now:
                existing.status = "open"
                existing.suppressed_until = None
            updated += 1
        else:
            session.add(SecurityFinding(**f, ingestion_id=ingestion_id,
                                        first_seen=now, last_seen=now))
            created += 1

    session.add(FindingIngestion(
        ingestion_id=ingestion_id, source_tool=source_tool, source_format=source_format,
        asset_name=asset_name, environment=environment, total=len(canonical),
        created=created, updated=updated, status="ok", created_by=created_by,
    ))
    await session.commit()
    logger.info("Ingestão %s: %d total, %d novos, %d atualizados",
                ingestion_id, len(canonical), created, updated)
    return {"ingestion_id": ingestion_id, "total": len(canonical),
            "created": created, "updated": updated}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def overview(session: AsyncSession) -> dict[str, Any]:
    """Agregações para o dashboard de Security Ops."""
    def _group(col):
        return select(col, func.count()).select_from(SecurityFinding).where(
            SecurityFinding.status == "open").group_by(col)

    by_sev = {r[0]: r[1] for r in (await session.execute(_group(SecurityFinding.severity))).all()}
    by_cat = {r[0]: r[1] for r in (await session.execute(_group(SecurityFinding.category))).all()}
    by_asset = {r[0]: r[1] for r in (await session.execute(_group(SecurityFinding.asset_type))).all()}
    by_env = {r[0]: r[1] for r in (await session.execute(_group(SecurityFinding.environment))).all()}
    total_open = sum(by_sev.values())
    suppressed = (await session.execute(
        select(func.count()).select_from(SecurityFinding).where(SecurityFinding.status == "suppressed")
    )).scalar_one()

    # fila "corrigir primeiro" — maior risco, aberto, com correção disponível
    fix_first = (await session.execute(
        select(SecurityFinding).where(SecurityFinding.status == "open")
        .order_by(SecurityFinding.risk_score.desc(), SecurityFinding.last_seen.desc()).limit(10)
    )).scalars().all()

    return {
        "total_open": total_open,
        "suppressed": suppressed,
        "by_severity": by_sev,
        "by_category": by_cat,
        "by_asset_type": by_asset,
        "by_environment": by_env,
        "fix_first": [_row(f) for f in fix_first],
    }


def _row(f: SecurityFinding) -> dict[str, Any]:
    return {
        "id": f.id, "title": f.title, "severity": f.severity, "risk_score": f.risk_score,
        "risk_band": f.risk_band, "category": f.category, "asset_type": f.asset_type,
        "asset_name": f.asset_name, "environment": f.environment, "cve": f.cve,
        "package_name": f.package_name, "fixed_version": f.fixed_version,
        "status": f.status, "source_tool": f.source_tool, "occurrences": f.occurrences,
        "last_seen": f.last_seen, "first_seen": f.first_seen,
    }


def detail(f: SecurityFinding) -> dict[str, Any]:
    d = _row(f)
    d.update({
        "description": f.description, "evidence": f.evidence, "remediation": f.remediation,
        "references": f.references, "cwe": f.cwe, "cvss": f.cvss,
        "installed_version": f.installed_version, "file_path": f.file_path,
        "config_path": f.config_path, "host_name": f.host_name, "service_name": f.service_name,
        "exploit_available": f.exploit_available, "internet_exposed": f.internet_exposed,
        "privileged_context": f.privileged_context, "remediation_state": f.remediation_state,
        "assignee": f.assignee, "suppressed_until": f.suppressed_until,
        "suppression_reason": f.suppression_reason, "suppressed_by": f.suppressed_by,
        "tags": f.tags, "ingestion_id": f.ingestion_id,
    })
    return d
