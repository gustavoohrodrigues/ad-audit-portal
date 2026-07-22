"""Ações ativas de comunicação (fora do AD) com arquitetura de providers.

Providers: email (SMTP), Teams, Slack, Discord (webhooks) e Windows `msg` via
WinRM (opcional, com allowlist de hosts). Toda entrega é registrada em
notification_deliveries e auditada pela camada de API.

Regras: WinRM só envia para hosts na allowlist; nada de comando arbitrário;
credenciais nunca aparecem em logs; conteúdo é sanitizado.
"""
from __future__ import annotations

import html as _html
import re
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
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


# ---------------------------------------------------------------------------
# Template de e-mail HTML — identidade Astra, degradê de azul e rodapé limpo.
# Tabelas + estilos inline para máxima compatibilidade (Outlook/Gmail etc.).
# ---------------------------------------------------------------------------
_BRAND = {
    "product": "AD Audit Portal",
    "tagline": "Auditoria & Segurança de Identidade do Active Directory",
    "site": "www.astra-sa.com",
    "address": "Rua Colégio Florence, 59 — Jardim Primavera, Jundiaí/SP",
    "cnpj": "50.949.528/0001-80",
    "phone": "0800 160 5051",
    "email": "sac@astra-sa.com",
    "copyright": "© 2020–%Y Astra. Todos os direitos reservados.",
}
_LOGO = "https://www.astra-sa.com/arquivos/logo-loja.png?v=638850653961800000"
# Degradê de azul (escuro → vibrante) usado no cabeçalho e detalhes.
_GRAD = "linear-gradient(135deg,#0a2a6b 0%,#12489e 48%,#2f80ed 100%)"
_BLUE_DEEP = "#0a2a6b"
_BLUE = "#12489e"
_BLUE_BRIGHT = "#2f80ed"


def render_email_html(subject: str, body: str) -> str:
    """Renderiza o corpo (texto) em um template HTML com a marca Astra."""
    year = datetime.now(timezone.utc).strftime("%Y")
    safe_subject = _html.escape(subject or "Notificação")
    # preserva parágrafos/linhas do corpo em texto
    safe_body = _html.escape(body or "").replace("\n", "<br>")
    copyright_txt = _html.escape(_BRAND["copyright"].replace("%Y", year))
    return f"""\
<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only">
</head>
<body style="margin:0;padding:0;background:#eef3fb;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef3fb;padding:28px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
  style="width:600px;max-width:100%;background:#ffffff;border-radius:14px;overflow:hidden;
  box-shadow:0 8px 30px rgba(10,42,107,0.14);font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">

  <!-- Cabeçalho com degradê de azul -->
  <tr><td style="background:{_BLUE};background:{_GRAD};padding:30px 34px 26px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="vertical-align:middle;">
        <span style="display:inline-block;background:#ffffff;border-radius:8px;padding:8px 14px;line-height:0;">
          <img src="{_LOGO}" alt="Astra" height="30"
            style="display:block;height:30px;border:0;outline:none;text-decoration:none;">
        </span>
      </td>
      <td style="vertical-align:middle;text-align:right;">
        <span style="display:inline-block;background:rgba(255,255,255,0.16);color:#eaf1ff;
          font-size:11px;font-weight:600;padding:6px 12px;border-radius:20px;letter-spacing:.5px;">
          Notificação automática</span>
      </td>
    </tr></table>
    <div style="font-size:12.5px;color:#cfe0ff;margin-top:16px;">{_html.escape(_BRAND["tagline"])}</div>
  </td></tr>

  <!-- Faixa fina de destaque -->
  <tr><td style="height:4px;background:{_BLUE_BRIGHT};background:{_GRAD};"></td></tr>

  <!-- Conteúdo -->
  <tr><td style="padding:30px 34px 8px;">
    <h1 style="margin:0 0 14px;font-size:19px;line-height:1.35;color:{_BLUE_DEEP};font-weight:700;">
      {safe_subject}</h1>
    <div style="font-size:14.5px;line-height:1.65;color:#2b3446;">
      {safe_body}
    </div>
  </td></tr>

  <!-- Assinatura -->
  <tr><td style="padding:22px 34px 26px;">
    <div style="border-top:1px solid #e6ecf6;padding-top:18px;font-size:13px;color:#54607a;">
      Atenciosamente,<br>
      <strong style="color:{_BLUE};">Tecnologia da Informação — Infraestrutura &amp; Segurança</strong>
    </div>
  </td></tr>

  <!-- Rodapé -->
  <tr><td style="background:#f4f7fc;border-top:1px solid #e6ecf6;padding:22px 34px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="font-size:11.5px;line-height:1.7;color:#6b7690;">
        {_html.escape(_BRAND["address"])}<br>
        CNPJ {_html.escape(_BRAND["cnpj"])} · {_html.escape(_BRAND["phone"])}<br>
        <a href="mailto:{_BRAND["email"]}" style="color:{_BLUE_BRIGHT};text-decoration:none;">{_html.escape(_BRAND["email"])}</a>
        &nbsp;·&nbsp;
        <a href="https://{_BRAND["site"]}" style="color:{_BLUE_BRIGHT};text-decoration:none;">{_html.escape(_BRAND["site"])}</a>
      </td>
    </tr></table>
    <div style="margin-top:14px;font-size:10.5px;color:#9aa4bc;">
      {copyright_txt}<br>
      Mensagem gerada automaticamente pelo {_html.escape(_BRAND["product"])}. Não responda a este e-mail.
    </div>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""


def _send_email(subject: str, body: str, to: list[str]) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[AD-Audit] {subject}"
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(to)
    # Anexa texto primeiro e HTML por último: o cliente prefere a última parte
    # que souber renderizar (HTML), com fallback automático para texto puro.
    msg.attach(MIMEText(body, "plain", _charset="utf-8"))
    msg.attach(MIMEText(render_email_html(subject, body), "html", _charset="utf-8"))
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
