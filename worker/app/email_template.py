"""Template de e-mail HTML com a identidade Astra (degradê de azul).

Cópia self-contained para o worker (imagem separada do backend). Mantenha em
sincronia com backend/app/services/messaging.py::render_email_html.
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone

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
_GRAD = "linear-gradient(135deg,#0a2a6b 0%,#12489e 48%,#2f80ed 100%)"
_BLUE_DEEP = "#0a2a6b"
_BLUE = "#12489e"
_BLUE_BRIGHT = "#2f80ed"


def render_email_html(subject: str, body: str) -> str:
    year = datetime.now(timezone.utc).strftime("%Y")
    safe_subject = _html.escape(subject or "Notificação")
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

  <tr><td style="height:4px;background:{_BLUE_BRIGHT};background:{_GRAD};"></td></tr>

  <tr><td style="padding:30px 34px 8px;">
    <h1 style="margin:0 0 14px;font-size:19px;line-height:1.35;color:{_BLUE_DEEP};font-weight:700;">
      {safe_subject}</h1>
    <div style="font-size:14.5px;line-height:1.65;color:#2b3446;">
      {safe_body}
    </div>
  </td></tr>

  <tr><td style="padding:22px 34px 26px;">
    <div style="border-top:1px solid #e6ecf6;padding-top:18px;font-size:13px;color:#54607a;">
      Atenciosamente,<br>
      <strong style="color:{_BLUE};">Tecnologia da Informação — Infraestrutura &amp; Segurança</strong>
    </div>
  </td></tr>

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
