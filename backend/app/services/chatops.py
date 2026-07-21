"""ChatOps: alertas automáticos de saúde e envio de relatórios para o Google Chat.

Reusa o motor de saúde (services/health), os webhooks cadastrados (chat_webhooks)
e os cards do Google Chat (services/messaging). Deduplicação via Redis para não
inundar os canais.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.core.redis_client import redis_client
from app.models.analytics import ChatWebhook
from app.services import messaging
from app.services.health import evaluate

logger = get_logger(__name__)
settings = get_settings()

_STATE_KEY = "chatops:health:last"          # último status enviado
_SIG_KEY = "chatops:health:sig"             # assinatura dos checks de erro


async def _enabled_webhooks(session: AsyncSession, health_only: bool = False) -> list[ChatWebhook]:
    stmt = select(ChatWebhook).where(
        ChatWebhook.enabled.is_(True), ChatWebhook.provider == "google_chat"
    )
    if health_only:
        stmt = stmt.where(ChatWebhook.health_alerts.is_(True))
    return list((await session.execute(stmt)).scalars().all())


def _status_emoji(status: str) -> str:
    # símbolo textual (sem emoji gráfico) para o card
    return {"HEALTH_OK": "OK", "HEALTH_WARN": "ATENCAO", "HEALTH_ERR": "CRITICO"}.get(status, status)


async def dispatch_health_alert(session: AsyncSession) -> dict:
    """Avalia a saúde e envia card ao Google Chat quando piora / recupera.

    Regras:
    - Envia quando o status é HEALTH_ERR e a assinatura dos erros muda, OU
      quando muda de OK/WARN para ERR.
    - Envia um card de recuperação quando volta de ERR para OK.
    - Rate-limit implícito pela assinatura (não repete o mesmo conjunto de erros).
    """
    muted = set(await redis_client.smembers("health:muted"))
    health = await evaluate(session, muted)
    status = health["status"]

    active = [c for c in health["checks"] if not c["muted"] and c["severity"] != "ok"]
    errors = [c for c in active if c["severity"] == "error"]
    sig = hashlib.sha256(
        ",".join(sorted(c["id"] for c in errors)).encode()
    ).hexdigest()[:16]

    last_status = await redis_client.get(_STATE_KEY)
    last_sig = await redis_client.get(_SIG_KEY)

    webhooks = await _enabled_webhooks(session, health_only=True)
    result = {"status": status, "sent": 0, "webhooks": len(webhooks), "action": "none"}

    # nada a fazer se não há webhooks configurados
    if not webhooks:
        await redis_client.set(_STATE_KEY, status)
        await redis_client.set(_SIG_KEY, sig)
        return result

    send = False
    action = "none"
    if status == "HEALTH_ERR" and sig != last_sig:
        send, action = True, "error"
    elif status == "HEALTH_OK" and last_status == "HEALTH_ERR":
        send, action = True, "recovered"

    if send:
        if action == "recovered":
            card = messaging.build_chat_card(
                title="AD Audit — Saúde recuperada",
                subtitle="Status: HEALTH_OK",
                items=[{"label": "Situação", "text": "Todos os problemas críticos foram resolvidos."}],
                link={"text": "Abrir painel de Saúde", "url": f"{settings.app_url}/health"},
            )
        else:
            items = [{"label": _status_emoji(c["severity"]), "text": c["summary"]}
                     for c in (errors + [c for c in active if c["severity"] == "warning"])[:8]]
            card = messaging.build_chat_card(
                title="AD Audit — Alerta de Saúde",
                subtitle=f"Status: {status} · {health['summary']['error']} erro(s), {health['summary']['warning']} aviso(s)",
                items=items,
                link={"text": "Investigar no portal", "url": f"{settings.app_url}/health"},
            )
        for wh in webhooks:
            r = messaging.send_chat_card(wh.url, card)
            if r.ok:
                result["sent"] += 1
        result["action"] = action
        logger.info("ChatOps health alert (%s) enviado a %d webhook(s)", action, result["sent"])

    await redis_client.set(_STATE_KEY, status)
    await redis_client.set(_SIG_KEY, sig)
    return result


async def send_report_to_chat(session: AsyncSession, key: str, webhook_id: int) -> dict:
    """Gera o relatório e envia um card-resumo para o webhook indicado."""
    from app.services import reports as rp

    wh = await session.get(ChatWebhook, webhook_id)
    if not wh or not wh.enabled or wh.provider != "google_chat":
        return {"ok": False, "message": "Webhook inválido/desabilitado"}

    data = await rp.generate(session, key)
    items: list[dict] = []
    if data.get("summary"):
        for k, v in list(data["summary"].items())[:8]:
            items.append({"label": k.replace("_", " "), "text": str(v)})
    else:
        items.append({"label": "Registros", "text": str(data["total"])})
        # mostra as primeiras linhas resumidas
        cols = [c["field"] for c in data["columns"]][:2]
        for row in data["rows"][:5]:
            items.append({"label": str(row.get(cols[0], "")), "text": str(row.get(cols[1], "")) if len(cols) > 1 else ""})

    card = messaging.build_chat_card(
        title=f"Relatório: {data['title']}",
        subtitle=f"{data['total']} registro(s) · {data['category']}",
        items=items,
        link={"text": "Abrir portal", "url": f"{settings.app_url}/reports"},
    )
    r = messaging.send_chat_card(wh.url, card)
    return {"ok": r.ok, "message": r.message, "correlation_id": r.correlation_id, "webhook": wh.name}
