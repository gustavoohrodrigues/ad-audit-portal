"""Endpoints administrativos: conectores, teste, auditoria interna, retenção.
Todos exigem role administrator (exceto leitura de auditoria = security)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import CurrentUser, require_capability, require_role
from app.database import get_session
from app.ldap.client import ReadOnlyLDAP
from app.models.enums import Role
from app.models.ops import EventSource, InternalAuditLog, RetentionPolicy
from app.schemas import ConnectorTestRequest, ConnectorTestResult

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


@router.get("/connectors")
async def list_connectors(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    rows = (await session.execute(select(EventSource))).scalars().all()
    return {
        "mode": settings.event_collector_mode,
        "sources": [
            {
                "name": s.name,
                "type": s.connector_type,
                "enabled": s.enabled,
                "status": s.status,
                "last_event_at": s.last_event_at,
                "events_ingested": s.events_ingested,
                "errors_count": s.errors_count,
                "last_error": s.last_error,
            }
            for s in rows
        ],
    }


@router.post("/connectors/test", response_model=ConnectorTestResult)
async def test_connector(
    payload: ConnectorTestRequest,
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> ConnectorTestResult:
    ctype = payload.connector_type.lower()
    if ctype in ("ldap", "ad"):
        ok, msg = ReadOnlyLDAP(settings).test_connection()
        return ConnectorTestResult(ok=ok, message=msg)
    # Demais conectores: verificação de configuração presente.
    known = {"wef", "winrm", "elastic", "wazuh", "graylog", "splunk", "api"}
    if ctype not in known:
        return ConnectorTestResult(ok=False, message=f"Conector desconhecido: {ctype}")
    return ConnectorTestResult(
        ok=True,
        message=f"Conector '{ctype}' reconhecido. Teste ativo executado pelo collector.",
    )


@router.get("/audit-logs")
async def audit_logs(
    action: str | None = None,
    actor: str | None = None,
    limit: int = 200,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("critical:read")),
) -> dict:
    stmt = select(InternalAuditLog)
    if action:
        stmt = stmt.where(InternalAuditLog.action == action)
    if actor:
        stmt = stmt.where(InternalAuditLog.actor == actor)
    stmt = stmt.order_by(InternalAuditLog.created_at.desc()).limit(min(limit, 1000))
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "time": r.created_at,
                "actor": r.actor,
                "role": r.actor_role,
                "action": r.action,
                "resource": r.resource,
                "ip": r.ip_address,
                "success": r.success,
            }
            for r in rows
        ]
    }


@router.post("/sync/ad-users")
async def trigger_ad_sync(
    scope: str = "all",
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    """Dispara a sincronização do AD (somente leitura). scope: all|users|groups|computers."""
    from app.services.ad_sync import (
        sync_all,
        sync_computers,
        sync_groups,
        sync_users,
    )

    if scope == "users":
        return await sync_users(session)
    if scope == "groups":
        return await sync_groups(session)
    if scope == "computers":
        return await sync_computers(session)
    return await sync_all(session)


def _mask(value: str) -> str:
    if not value:
        return ""
    return value if len(value) < 6 else value[:3] + "***"


@router.get("/integrations")
async def list_integrations(
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    """Status das integrações (sem expor segredos)."""
    s = settings
    integrations = [
        {
            "key": "ldap", "name": "Active Directory (LDAPS)", "category": "core",
            "enabled": s.ad_enabled, "endpoint": s.ad_ldap_uri, "testable": True,
        },
        {
            "key": "smtp", "name": "E-mail (SMTP)", "category": "alerta",
            "enabled": s.alert_email_enabled,
            "endpoint": f"{s.smtp_host}:{s.smtp_port}" if s.smtp_host else "",
            "testable": True,
        },
        {
            "key": "webhook", "name": "Webhook", "category": "alerta",
            "enabled": s.webhook_enabled, "endpoint": s.webhook_url, "testable": True,
        },
        {
            "key": "glpi", "name": "GLPI (tickets)", "category": "itsm",
            "enabled": s.glpi_enabled, "endpoint": s.glpi_url, "testable": True,
        },
        {
            "key": "zabbix", "name": "Zabbix (trapper)", "category": "observabilidade",
            "enabled": s.zabbix_enabled,
            "endpoint": f"{s.zabbix_server}:{s.zabbix_trapper_port}" if s.zabbix_server else "",
            "testable": False,
        },
        {
            "key": "prometheus", "name": "Prometheus (métricas)", "category": "observabilidade",
            "enabled": s.prometheus_enabled, "endpoint": s.prometheus_metrics_path,
            "testable": True,
        },
        {
            "key": "teams", "name": "Microsoft Teams", "category": "chatops",
            "enabled": False, "endpoint": "", "testable": False, "roadmap": True,
        },
        {
            "key": "slack", "name": "Slack", "category": "chatops",
            "enabled": False, "endpoint": "", "testable": False, "roadmap": True,
        },
        {
            "key": "discord", "name": "Discord", "category": "chatops",
            "enabled": False, "endpoint": "", "testable": False, "roadmap": True,
        },
    ]
    return {"integrations": integrations}


@router.post("/integrations/{key}/test", response_model=ConnectorTestResult)
async def test_integration(
    key: str,
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> ConnectorTestResult:
    s = settings
    if key == "ldap":
        ok, msg = ReadOnlyLDAP(s).test_connection()
        return ConnectorTestResult(ok=ok, message=msg)
    if key == "smtp":
        if not s.smtp_host:
            return ConnectorTestResult(ok=False, message="SMTP_HOST não configurado")
        import smtplib

        try:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=8) as srv:
                if s.smtp_use_tls:
                    srv.starttls()
                if s.smtp_username:
                    srv.login(s.smtp_username, s.smtp_password)
            return ConnectorTestResult(ok=True, message=f"SMTP OK ({s.smtp_host}:{s.smtp_port})")
        except Exception as exc:  # noqa: BLE001
            return ConnectorTestResult(ok=False, message=f"Falha SMTP: {exc}")
    if key in ("webhook", "glpi", "prometheus"):
        import httpx

        url = {"webhook": s.webhook_url, "glpi": s.glpi_url,
               "prometheus": s.prometheus_metrics_path}[key]
        if key == "prometheus":
            return ConnectorTestResult(ok=s.prometheus_enabled, message="Métricas expostas em /api/v1/metrics")
        if not url:
            return ConnectorTestResult(ok=False, message="Endpoint não configurado")
        try:
            with httpx.Client(timeout=8, verify=True) as c:
                r = c.get(url if key == "glpi" else url)
            return ConnectorTestResult(ok=r.status_code < 500, message=f"HTTP {r.status_code} de {url}")
        except Exception as exc:  # noqa: BLE001
            return ConnectorTestResult(ok=False, message=f"Falha: {exc}")
    return ConnectorTestResult(ok=False, message=f"Integração '{key}' não suporta teste ativo")


@router.post("/sync/full")
async def full_resync(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    """Full resync manual (ignora watermark). Protegido contra concorrência."""
    from app.core.redis_client import redis_client
    from app.services.ad_sync import sync_all

    lock = await redis_client.set("adsync:full:lock", "1", nx=True, ex=1800)
    if not lock:
        raise HTTPException(status_code=409, detail="Já existe um full sync em andamento")
    try:
        return await sync_all(session, force_full=True)
    finally:
        await redis_client.delete("adsync:full:lock")


@router.get("/sync/status")
async def sync_status(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("critical:read")),
) -> dict:
    from app.models.ops import ADSyncCheckpoint

    rows = (await session.execute(select(ADSyncCheckpoint))).scalars().all()
    return {
        "mode": settings.ad_sync_mode,
        "usn_changed_enabled": settings.ad_sync_usn_changed_enabled,
        "checkpoints": [
            {
                "source": c.source,
                "highest_usn": c.highest_usn,
                "last_full_sync_at": c.last_full_sync_at,
                "last_incremental_at": c.last_incremental_at,
                "updated_at": c.updated_at,
            }
            for c in rows
        ],
    }


@router.get("/retention")
async def get_retention(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    rows = (await session.execute(select(RetentionPolicy))).scalars().all()
    defaults = {
        "events": settings.event_retention_days,
        "raw_events": settings.event_raw_retention_days,
        "audit": settings.audit_log_retention_days,
    }
    configured = {r.data_type: r.retention_days for r in rows}
    return {"defaults": defaults, "configured": configured}
