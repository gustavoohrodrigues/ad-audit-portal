"""Autenticação: login (LDAP), refresh, logout, me. JWT + refresh token."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.core.metrics import login_attempts_total
from app.core.rbac import resolve_roles
from app.core.redis_client import (
    is_refresh_valid,
    revoke_refresh,
    store_refresh_jti,
)
from app.core.security import (
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    decode_token,
)
from app.database import get_session
from app.ldap.client import ReadOnlyLDAP
from app.schemas import (
    LoginRequest,
    MeResponse,
    MfaEnableRequest,
    MfaLoginRequest,
    MfaSetupResponse,
    MfaStatusResponse,
    TokenResponse,
)
from app.services import mfa as mfa_service
from app.services.audit import record_audit

import jwt

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)
settings = get_settings()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")


def _set_cookies(response: Response, access: str, refresh: str) -> None:
    common = dict(
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
    )
    response.set_cookie(
        "access_token",
        access,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        **common,
    )
    response.set_cookie(
        "refresh_token",
        refresh,
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        path="/api/v1/auth",
        **common,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")

    ldap = ReadOnlyLDAP(settings)
    user = ldap.authenticate(payload.username, payload.password)
    if not user:
        login_attempts_total.labels(result="failure").inc()
        await record_audit(
            session,
            actor=payload.username,
            action="login_failed",
            ip_address=ip,
            user_agent=ua,
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    roles = resolve_roles(user.get("groups", []))
    if not roles:
        # Usuário autenticou mas não pertence a nenhum grupo RBAC do portal.
        await record_audit(
            session,
            actor=user["sam_account_name"],
            action="login_denied_no_role",
            ip_address=ip,
            user_agent=ua,
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem grupo de autorização do portal",
        )

    subject = user["sam_account_name"]

    # Se o usuário tem MFA ativo, a senha está correta mas ainda falta o 2º fator.
    if await mfa_service.is_enabled(session, subject):
        await record_audit(
            session, actor=subject, action="login_mfa_challenge",
            ip_address=ip, user_agent=ua, success=True,
        )
        return TokenResponse(mfa_required=True, mfa_token=create_mfa_token(subject, roles))

    # MFA obrigatório por perfil mas ainda não configurado -> força cadastro
    enrollment_required = _mfa_enrollment_required(roles)
    return await _issue_tokens(
        session, response, subject, roles, ip, ua, mfa=False,
        enrollment_required=enrollment_required,
    )


def _mfa_enrollment_required(roles: list[str]) -> bool:
    required = set(settings.mfa_required_roles_list)
    return bool(required and required.intersection({r.lower() for r in roles}))


async def _issue_tokens(
    session: AsyncSession, response: Response, subject: str, roles: list[str],
    ip: str, ua: str, mfa: bool, enrollment_required: bool = False,
) -> TokenResponse:
    access = create_access_token(subject, roles)
    refresh, jti = create_refresh_token(subject, roles)
    await store_refresh_jti(jti, subject)
    _set_cookies(response, access, refresh)
    login_attempts_total.labels(result="success").inc()
    await record_audit(
        session, actor=subject, actor_role=roles[0] if roles else None,
        action="login", ip_address=ip, user_agent=ua, success=True,
        detail={"roles": roles, "mfa": mfa},
    )
    return TokenResponse(
        access_token=access,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        roles=roles,
        mfa_enrollment_required=enrollment_required,
    )


@router.post("/login/mfa", response_model=TokenResponse)
async def login_mfa(
    payload: MfaLoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")
    try:
        data = decode_token(payload.mfa_token, expected_type="mfa")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Desafio MFA expirado. Faça login novamente.")
    subject, roles = data["sub"], data.get("roles", [])
    if not await mfa_service.verify_login(session, subject, payload.code):
        login_attempts_total.labels(result="mfa_failure").inc()
        await record_audit(
            session, actor=subject, action="login_mfa_failed",
            ip_address=ip, user_agent=ua, success=False,
        )
        raise HTTPException(status_code=401, detail="Código MFA inválido")
    return await _issue_tokens(session, response, subject, roles, ip, ua, mfa=True)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, response: Response) -> TokenResponse:
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token ausente")
    try:
        payload = decode_token(token, expected_type="refresh")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Refresh token inválido")

    jti, subject = payload.get("jti"), payload.get("sub")
    if not await is_refresh_valid(jti, subject):
        raise HTTPException(status_code=401, detail="Refresh token revogado")

    # rotação de refresh token
    await revoke_refresh(jti)
    roles = payload.get("roles") or []
    if not roles:
        # sem roles no refresh; força novo login para reobter grupos do AD
        raise HTTPException(status_code=401, detail="Faça login novamente")
    access = create_access_token(subject, roles)
    new_refresh, new_jti = create_refresh_token(subject, roles)
    await store_refresh_jti(new_jti, subject)
    _set_cookies(response, access, new_refresh)
    return TokenResponse(
        access_token=access,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        roles=roles,
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    token = request.cookies.get("refresh_token")
    if token:
        try:
            payload = decode_token(token, expected_type="refresh")
            await revoke_refresh(payload.get("jti"))
        except jwt.InvalidTokenError:
            pass
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    await record_audit(
        session,
        actor=user.username,
        actor_role=user.role,
        action="logout",
        ip_address=_client_ip(request),
    )
    return {"status": "logged_out"}


@router.get("/me", response_model=MeResponse)
async def me(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> MeResponse:
    enabled = await mfa_service.is_enabled(session, user.username)
    enrollment = _mfa_enrollment_required(user.roles) and not enabled
    return MeResponse(
        username=user.username, roles=user.roles, role=user.role,
        mfa_enabled=enabled, mfa_enrollment_required=enrollment,
    )


# --------------------------- MFA (TOTP) ---------------------------
@router.get("/mfa/status", response_model=MfaStatusResponse)
async def mfa_status(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> MfaStatusResponse:
    row = await mfa_service.get_mfa(session, user.username)
    return MfaStatusResponse(enabled=bool(row and row.enabled), configured=bool(row))


@router.post("/mfa/setup", response_model=MfaSetupResponse)
async def mfa_setup(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> MfaSetupResponse:
    try:
        data = await mfa_service.start_setup(session, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return MfaSetupResponse(**data)


@router.post("/mfa/enable")
async def mfa_enable(
    payload: MfaEnableRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        result = await mfa_service.enable(session, user.username, payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await record_audit(
        session, actor=user.username, actor_role=user.role,
        action="mfa_enabled", ip_address=_client_ip(request),
    )
    return result


@router.post("/mfa/disable")
async def mfa_disable(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    await mfa_service.disable(session, user.username)
    await record_audit(
        session, actor=user.username, actor_role=user.role,
        action="mfa_disabled", ip_address=_client_ip(request),
    )
    return {"disabled": True}
