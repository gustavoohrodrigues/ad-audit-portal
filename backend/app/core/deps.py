"""Dependências FastAPI: usuário autenticado, checagem de role e capacidade."""
from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.rbac import has_capability, highest_role
from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    username: str
    roles: list[str]

    @property
    def role(self) -> str | None:
        return highest_role(self.roles)


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> CurrentUser:
    token = creds.credentials if creds else None
    # também aceita cookie httpOnly (frontend usa cookie seguro)
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado"
        )
    try:
        payload = decode_token(token, expected_type="access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        )
    return CurrentUser(username=payload["sub"], roles=payload.get("roles", []))


def require_capability(capability: str):
    """Factory de dependência que exige uma capacidade RBAC específica."""

    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not has_capability(user.roles, capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado: requer capacidade '{capability}'",
            )
        return user

    return _dep


def require_role(*roles: str):
    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(r in user.roles for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: perfil insuficiente",
            )
        return user

    return _dep
