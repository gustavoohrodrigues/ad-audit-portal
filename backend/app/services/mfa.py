"""Serviço de MFA baseado em TOTP (compatível com Google/Microsoft Authenticator).

O segredo é gerado por usuário e só é 'enabled' após o usuário confirmar um
código válido. Gera também o QR Code (otpauth://) como data URI para exibição.
Códigos de backup de uso único são fornecidos na ativação.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

import pyotp
import segno
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.security import UserMFA

settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(username: str, secret: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=username, issuer_name=settings.app_name
    )


def qr_data_uri(uri: str) -> str:
    """Gera o QR Code do otpauth URI como data URI PNG (para <img src>)."""
    qr = segno.make(uri, error="m")
    import io

    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=5, dark="#0a0a0a", light="#ffffff", border=2)
    import base64

    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def verify_code(secret: str, code: str) -> bool:
    if not code:
        return False
    code = code.strip().replace(" ", "")
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_backup_codes(n: int = 8) -> list[str]:
    return [f"{secrets.randbelow(1_000_000):06d}" for _ in range(n)]


async def get_mfa(session: AsyncSession, username: str) -> UserMFA | None:
    return (
        await session.execute(
            select(UserMFA).where(UserMFA.sam_account_name == username)
        )
    ).scalars().first()


async def is_enabled(session: AsyncSession, username: str) -> bool:
    row = await get_mfa(session, username)
    return bool(row and row.enabled)


async def start_setup(session: AsyncSession, username: str) -> dict:
    """Cria/renova o segredo (ainda não habilitado) e retorna QR + URI."""
    row = await get_mfa(session, username)
    secret = generate_secret()
    if row and row.enabled:
        raise ValueError("MFA já está ativo para este usuário")
    if row:
        row.secret = secret
        row.updated_at = _now()
    else:
        row = UserMFA(sam_account_name=username, secret=secret, enabled=False)
        session.add(row)
    await session.commit()
    uri = provisioning_uri(username, secret)
    return {"secret": secret, "otpauth_uri": uri, "qr_data_uri": qr_data_uri(uri)}


async def enable(session: AsyncSession, username: str, code: str) -> dict:
    row = await get_mfa(session, username)
    if not row:
        raise ValueError("Inicie a configuração do MFA antes de ativar")
    if not verify_code(row.secret, code):
        raise ValueError("Código inválido")
    codes = generate_backup_codes()
    row.enabled = True
    row.confirmed_at = _now()
    row.backup_codes = codes
    row.updated_at = _now()
    session.add(row)
    await session.commit()
    return {"enabled": True, "backup_codes": codes}


async def verify_login(session: AsyncSession, username: str, code: str) -> bool:
    row = await get_mfa(session, username)
    if not row or not row.enabled:
        return False
    if verify_code(row.secret, code):
        return True
    # tenta código de backup (uso único)
    normalized = (code or "").strip()
    if normalized in (row.backup_codes or []):
        row.backup_codes = [c for c in row.backup_codes if c != normalized]
        session.add(row)
        await session.commit()
        return True
    return False


async def disable(session: AsyncSession, username: str) -> None:
    row = await get_mfa(session, username)
    if row:
        await session.delete(row)
        await session.commit()
