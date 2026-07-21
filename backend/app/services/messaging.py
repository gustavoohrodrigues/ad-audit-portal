"""Ações ativas de comunicação (fora do AD) com arquitetura de providers.

Providers: email (SMTP), Teams, Slack, Discord (webhooks) e Windows `msg` via
WinRM (opcional, com allowlist de hosts). Toda entrega é registrada em
notification_deliveries e auditada pela camada de API.

Regras: WinRM só envia para hosts na allowlist; nada de comando arbitrário;
credenciais nunca aparecem em logs; conteúdo é sanitizado.
"""
from __future__ import annotations

import re
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.text import MIMEText

import httpx

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

VALID_CHANNELS = {"email", "teams", "slack", "discord", "winrm"}
# sanitização: remove caracteres de controle e limita tamanho
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
# hostname/FQDN/IP válido (evita injeção no alvo do WinRM)
_HOST_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]{0,253}[a-zA-Z0-9])?$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def sanitize(text: str, limit: int = 2000) -> str:
    return _CTRL.sub("", (text or ""))[:limit]


def winrm_allowed_hosts() -> set[str]:
    return {h.strip().lower() for h in settings.message_winrm_allowed_hosts.split(",") if h.strip()}


class DeliveryResult:
    def __init__(self, ok: bool, message: str, correlation_id: str):
        self.ok = ok
        self.message = message
        self.correlation_id = correlation_id


def _send_email(subject: str, body: str, to: list[str]) -> None:
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = f"[AD-Audit] {subject}"
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(to)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as srv:
        if settings.smtp_use_tls:
            srv.starttls()
        if settings.smtp_username:
            srv.login(settings.smtp_username, settings.smtp_password)
        srv.sendmail(settings.smtp_from, to, msg.as_string())


def _post_webhook(url: str, payload: dict) -> None:
    with httpx.Client(timeout=10, verify=True) as c:
        r = c.post(url, json=payload)
        r.raise_for_status()


def is_google_chat_url(url: str) -> bool:
    return url.startswith("https://chat.googleapis.com/")


def send_to_chat_webhook(url: str, subject: str, body: str) -> DeliveryResult:
    """Envia uma mensagem simples (texto) para um webhook do Google Chat."""
    cid = str(uuid.uuid4())
    subject = sanitize(subject, 200)
    body = sanitize(body)
    try:
        if not settings.notifications_enabled:
            return DeliveryResult(False, "Notificações desabilitadas", cid)
        if not is_google_chat_url(url):
            return DeliveryResult(False, "URL de webhook do Google Chat inválida", cid)
        text = f"*{subject}*\n{body}" if subject else body
        _post_webhook(url, {"text": text})
        return DeliveryResult(True, "Enviado", cid)
    except Exception as exc:  # noqa: BLE001
        return DeliveryResult(False, f"Falha no envio: {type(exc).__name__}", cid)


def build_chat_card(
    title: str,
    subtitle: str = "",
    items: list[dict] | None = None,
    link: dict | None = None,
) -> dict:
    """Monta um cardsV2 do Google Chat.

    items: [{"label": "...", "text": "..."}]  link: {"text": "...", "url": "..."}
    """
    widgets: list[dict] = []
    for it in (items or []):
        widgets.append({"decoratedText": {
            "topLabel": sanitize(str(it.get("label", "")), 60),
            "text": sanitize(str(it.get("text", "")), 400),
            "wrapText": True,
        }})
    if link and link.get("url"):
        widgets.append({"buttonList": {"buttons": [{
            "text": sanitize(str(link.get("text", "Abrir")), 40),
            "onClick": {"openLink": {"url": link["url"]}},
        }]}})
    sections = [{"widgets": widgets}] if widgets else []
    return {"cardsV2": [{
        "cardId": str(uuid.uuid4()),
        "card": {
            "header": {"title": sanitize(title, 120), "subtitle": sanitize(subtitle, 120)},
            "sections": sections,
        },
    }]}


def send_chat_card(url: str, card: dict) -> DeliveryResult:
    """Envia um card rico (cardsV2) para um webhook do Google Chat."""
    cid = str(uuid.uuid4())
    try:
        if not settings.notifications_enabled:
            return DeliveryResult(False, "Notificações desabilitadas", cid)
        if not is_google_chat_url(url):
            return DeliveryResult(False, "URL de webhook do Google Chat inválida", cid)
        _post_webhook(url, card)
        return DeliveryResult(True, "Enviado", cid)
    except Exception as exc:  # noqa: BLE001
        return DeliveryResult(False, f"Falha no envio: {type(exc).__name__}", cid)


def _send_winrm_msg(host: str, message: str) -> None:
    """Envia mensagem via `msg` (WinRM). Host deve estar na allowlist."""
    import winrm  # type: ignore

    proto = "https" if settings.winrm_use_ssl else "http"
    sess = winrm.Session(
        f"{proto}://{host}:{settings.winrm_port}/wsman",
        auth=(settings.winrm_username, settings.winrm_password),
        transport=settings.winrm_transport,
        server_cert_validation="validate" if settings.winrm_verify_tls else "ignore",
    )
    # msg * envia a todas as sessões do host; conteúdo sanitizado e sem interpolação de comando
    safe = message.replace('"', "'")
    r = sess.run_cmd("msg", ["*", f"/TIME:{settings.message_winrm_timeout_seconds}", safe])
    if r.status_code != 0:
        raise RuntimeError(r.std_err.decode("utf-8", "replace")[:160])


def deliver(
    channel: str,
    subject: str,
    body: str,
    target: str | None = None,
) -> DeliveryResult:
    """Executa o envio no canal indicado. Retorna DeliveryResult (não levanta)."""
    cid = str(uuid.uuid4())
    channel = channel.lower()
    subject = sanitize(subject, 200)
    body = sanitize(body)

    try:
        if channel not in VALID_CHANNELS:
            return DeliveryResult(False, f"Canal inválido: {channel}", cid)
        if not settings.notifications_enabled:
            return DeliveryResult(False, "Notificações desabilitadas (NOTIFICATIONS_ENABLED=false)", cid)

        if channel == "email":
            recipients = [target] if target else settings.smtp_to.split(",")
            recipients = [r.strip() for r in recipients if r.strip()]
            if not recipients:
                return DeliveryResult(False, "Sem destinatário de e-mail", cid)
            _send_email(subject, body, recipients)

        elif channel == "teams":
            if not (settings.teams_enabled and settings.teams_webhook_url):
                return DeliveryResult(False, "Teams não configurado", cid)
            _post_webhook(settings.teams_webhook_url, {"text": f"**{subject}**\n\n{body}"})

        elif channel == "slack":
            if not (settings.slack_enabled and settings.slack_webhook_url):
                return DeliveryResult(False, "Slack não configurado", cid)
            _post_webhook(settings.slack_webhook_url, {"text": f"*{subject}*\n{body}"})

        elif channel == "discord":
            if not (settings.discord_enabled and settings.discord_webhook_url):
                return DeliveryResult(False, "Discord não configurado", cid)
            _post_webhook(settings.discord_webhook_url, {"content": f"**{subject}**\n{body}"})

        elif channel == "winrm":
            if not settings.message_winrm_enabled:
                return DeliveryResult(False, "WinRM msg desabilitado", cid)
            host = (target or "").strip().lower()
            if not host:
                return DeliveryResult(False, "Host de destino é obrigatório", cid)
            if not _HOST_RE.match(host):
                return DeliveryResult(False, "Host de destino inválido", cid)
            # allowlist só é exigida se MESSAGE_WINRM_ALLOW_ANY_HOST=false
            if not settings.message_winrm_allow_any_host and host not in winrm_allowed_hosts():
                return DeliveryResult(False, f"Host '{target}' não está na allowlist", cid)
            try:
                import winrm  # noqa: F401
            except ImportError:
                return DeliveryResult(False, "pywinrm indisponível", cid)
            _send_winrm_msg(host, f"{subject}: {body}")

        logger.info("Notificação enviada", extra={"extra_fields": {"channel": channel, "cid": cid}})
        return DeliveryResult(True, "Enviado", cid)
    except Exception as exc:  # noqa: BLE001
        # erro sanitizado (sem credenciais)
        return DeliveryResult(False, f"Falha no envio: {type(exc).__name__}", cid)
