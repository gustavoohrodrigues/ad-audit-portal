"""Emissão e validação de JWT (access + refresh) e utilidades de token."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config import get_settings

settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, roles: list[str], extra: dict | None = None) -> str:
    now = _now()
    payload = {
        "sub": subject,
        "roles": roles,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return _encode(payload)


def create_refresh_token(subject: str, roles: list[str]) -> tuple[str, str]:
    """Retorna (token, jti). O jti é persistido no Redis para permitir revogação.

    As roles são incluídas no refresh para que a renovação de access token não
    dependa de nova consulta ao AD (que é reavaliada no próximo login completo).
    """
    now = _now()
    jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "roles": roles,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
        "jti": jti,
    }
    return _encode(payload), jti


def create_mfa_token(subject: str, roles: list[str]) -> str:
    """Token de pré-autenticação (curta duração) emitido após validar a senha,
    trocado por access/refresh depois da verificação do código MFA."""
    now = _now()
    payload = {
        "sub": subject,
        "roles": roles,
        "type": "mfa",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "jti": str(uuid.uuid4()),
    }
    return _encode(payload)


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    payload = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"tipo de token inválido: esperado {expected_type}")
    return payload
