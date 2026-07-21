"""Sincronização SOMENTE LEITURA de usuários do AD para a tabela ad_users.

Lê os objetos de conta via LDAP (paginado), converte os atributos (FILETIME,
SID, GUID, UAC) e faz upsert em ad_users. Nunca escreve no AD.

Usado tanto sob demanda (endpoint admin / script) quanto de forma agendada.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.ldap.client import ReadOnlyLDAP
from app.ldap.converters import (
    filetime_to_datetime,
    guid_to_string,
    parse_uac,
    sid_to_string,
)
from app.models.directory import ADComputer, ADGroup, ADUser

logger = get_logger(__name__)
settings = get_settings()

# Apenas contas de usuário (exclui computadores, que também são objectClass=user).
USER_FILTER = "(&(objectCategory=person)(objectClass=user))"
COMPUTER_FILTER = "(objectClass=computer)"
GROUP_FILTER = "(objectClass=group)"

COMPUTER_ATTRS = [
    "sAMAccountName", "dNSHostName", "distinguishedName", "operatingSystem",
    "whenCreated", "lastLogonTimestamp", "userAccountControl", "objectSid", "objectGUID",
]
GROUP_ATTRS = [
    "sAMAccountName", "displayName", "distinguishedName", "description",
    "member", "adminCount", "objectSid", "objectGUID",
]


def _ci(raw: dict) -> dict:
    """Índice case-insensitive dos atributos retornados pelo LDAP."""
    return {k.lower(): v for k, v in raw.items()}


def _one(idx: dict, key: str) -> str | None:
    vals = idx.get(key.lower())
    if not vals:
        return None
    v = vals[0]
    return v.decode("utf-8", "replace") if isinstance(v, (bytes, bytearray)) else str(v)


def _int(idx: dict, key: str) -> int | None:
    s = _one(idx, key)
    try:
        return int(s) if s is not None else None
    except ValueError:
        return None


def _filetime(idx: dict, key: str) -> datetime | None:
    return filetime_to_datetime(_one(idx, key))


def _list(idx: dict, key: str) -> list[str]:
    out = []
    for v in idx.get(key.lower(), []) or []:
        out.append(v.decode("utf-8", "replace") if isinstance(v, (bytes, bytearray)) else str(v))
    return out


def _raw_first(idx: dict, key: str) -> bytes | None:
    vals = idx.get(key.lower())
    if not vals:
        return None
    v = vals[0]
    return v if isinstance(v, (bytes, bytearray)) else None


def _generalized_time(idx: dict, key: str) -> datetime | None:
    """whenCreated/whenChanged: formato AD 'YYYYMMDDHHMMSS.0Z'."""
    s = _one(idx, key)
    if not s or len(s) < 14:
        return None
    try:
        return datetime.strptime(s[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _cn_set(dns: list[str]) -> set[str]:
    import re

    out = set()
    for dn in dns:
        m = re.match(r"^CN=([^,]+)", dn, re.IGNORECASE)
        out.add((m.group(1) if m else dn).lower())
    return out


def get_domain_max_pwd_age_days() -> float | None:
    """Lê o maxPwdAge da política de domínio (FILETIME negativo). None se 0/never."""
    ldap = ReadOnlyLDAP(settings)
    try:
        rows = ldap.search(settings.ad_base_dn, "(objectClass=domainDNS)", ["maxPwdAge"])
    except Exception:  # noqa: BLE001
        return None
    for r in rows:
        idx = _ci(r)
        raw = _one(idx, "maxPwdAge")
        if raw is None:
            continue
        try:
            val = int(raw)
        except ValueError:
            continue
        if val == 0:
            return None  # senhas nunca expiram por política
        return abs(val) / (10**7 * 86400)
    return None


def map_user(raw: dict, max_pwd_age_days: float | None = None) -> dict | None:
    idx = _ci(raw)
    sam = _one(idx, "sAMAccountName")
    sid = sid_to_string(_raw_first(idx, "objectSid"))
    if not sam or not sid:
        return None

    uac = _int(idx, "userAccountControl")
    flags = parse_uac(uac)
    member_of = _list(idx, "memberOf")
    groups = _cn_set(member_of)
    privileged_groups = {g.lower() for g in settings.privileged_groups_list}
    is_priv = bool(groups & privileged_groups) or (_int(idx, "adminCount") or 0) > 0

    last_logon = _filetime(idx, "lastLogonTimestamp") or _filetime(idx, "lastLogon")
    inactive_cut = datetime.now(timezone.utc) - timedelta(days=settings.inactive_account_days)
    is_inactive = bool(last_logon and last_logon < inactive_cut) and not flags.get("is_disabled")

    dn = _one(idx, "distinguishedName") or ""
    ou = ",".join(p for p in dn.split(",")[1:]) if dn else None

    # expiração de senha = última troca + política de domínio (se aplicável)
    pwd_last_set = _filetime(idx, "pwdLastSet")
    password_expires_at = None
    if (not flags.get("password_never_expires") and pwd_last_set and max_pwd_age_days
            and not flags.get("is_disabled")):
        password_expires_at = pwd_last_set + timedelta(days=max_pwd_age_days)

    return {
        "object_sid": sid,
        "object_guid": guid_to_string(_raw_first(idx, "objectGUID")),
        "sam_account_name": sam,
        "user_principal_name": _one(idx, "userPrincipalName"),
        "display_name": _one(idx, "displayName"),
        "given_name": _one(idx, "givenName"),
        "surname": _one(idx, "sn"),
        "mail": _one(idx, "mail"),
        "employee_id": _one(idx, "employeeID"),
        "department": _one(idx, "department"),
        "title": _one(idx, "title"),
        "manager": _one(idx, "manager"),
        "distinguished_name": dn or None,
        "ou": ou,
        "member_of": member_of,
        "user_account_control": uac,
        "admin_count": _int(idx, "adminCount"),
        "service_principal_name": _list(idx, "servicePrincipalName"),
        "allowed_to_delegate_to": _list(idx, "msDS-AllowedToDelegateTo"),
        "sid_history": [
            sid_to_string(v) for v in (idx.get("sidhistory") or [])
            if isinstance(v, (bytes, bytearray))
        ],
        "when_created": _generalized_time(idx, "whenCreated"),
        "when_changed": _generalized_time(idx, "whenChanged"),
        "pwd_last_set": pwd_last_set,
        "password_expires_at": password_expires_at,
        "last_logon_timestamp": last_logon,
        "account_expires": _filetime(idx, "accountExpires"),
        "lockout_time": _filetime(idx, "lockoutTime"),
        "bad_pwd_count": _int(idx, "badPwdCount"),
        "bad_password_time": _filetime(idx, "badPasswordTime"),
        "is_disabled": flags.get("is_disabled", False),
        "is_locked": flags.get("is_locked", False),
        "password_never_expires": flags.get("password_never_expires", False),
        "password_not_required": flags.get("password_not_required", False),
        "dont_require_preauth": flags.get("dont_require_preauth", False),
        "is_privileged": is_priv,
        "is_critical": sam.lower() in settings.critical_users_list,
        "is_inactive": is_inactive,
        "synced_at": datetime.now(timezone.utc),
    }


def _with_usn(base_filter: str, usn_filter: str | None) -> str:
    """Combina o filtro base com o filtro incremental de uSNChanged."""
    return f"(&{base_filter}{usn_filter})" if usn_filter else base_filter


async def sync_users(session: AsyncSession, usn_filter: str | None = None) -> dict:
    """Executa a sincronização e retorna estatísticas."""
    ldap = ReadOnlyLDAP(settings)
    base = settings.ad_users_search_base or settings.ad_base_dn
    max_pwd_age = get_domain_max_pwd_age_days()
    entries = ldap.search_users(_with_usn(USER_FILTER, usn_filter), base=base)
    logger.info(
        "AD sync: %d contas retornadas pelo LDAP (maxPwdAge=%s dias)",
        len(entries), round(max_pwd_age) if max_pwd_age else "nunca",
    )

    created = updated = skipped = 0
    for raw in entries:
        data = map_user(raw, max_pwd_age_days=max_pwd_age)
        if not data:
            skipped += 1
            continue
        existing = (
            await session.execute(
                select(ADUser).where(ADUser.object_sid == data["object_sid"])
            )
        ).scalars().first()
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            updated += 1
        else:
            session.add(ADUser(**data))
            created += 1
    await session.commit()
    result = {"total": len(entries), "created": created, "updated": updated, "skipped": skipped}
    logger.info("AD sync (usuários) concluído: %s", result)
    return result


def map_computer(raw: dict) -> dict | None:
    idx = _ci(raw)
    sid = sid_to_string(_raw_first(idx, "objectSid"))
    sam = _one(idx, "sAMAccountName")
    if not sid or not sam:
        return None
    flags = parse_uac(_int(idx, "userAccountControl"))
    return {
        "object_sid": sid,
        "object_guid": guid_to_string(_raw_first(idx, "objectGUID")),
        "sam_account_name": sam,
        "dns_host_name": _one(idx, "dNSHostName"),
        "distinguished_name": _one(idx, "distinguishedName"),
        "operating_system": _one(idx, "operatingSystem"),
        "when_created": _generalized_time(idx, "whenCreated"),
        "last_logon_timestamp": _filetime(idx, "lastLogonTimestamp"),
        "user_account_control": _int(idx, "userAccountControl"),
        "is_disabled": flags.get("is_disabled", False),
        "synced_at": datetime.now(timezone.utc),
    }


def map_group(raw: dict) -> dict | None:
    idx = _ci(raw)
    sid = sid_to_string(_raw_first(idx, "objectSid"))
    sam = _one(idx, "sAMAccountName")
    if not sid or not sam:
        return None
    members = _list(idx, "member")
    privileged_groups = {g.lower() for g in settings.privileged_groups_list}
    is_priv = sam.lower() in privileged_groups or (_int(idx, "adminCount") or 0) > 0
    return {
        "object_sid": sid,
        "object_guid": guid_to_string(_raw_first(idx, "objectGUID")),
        "sam_account_name": sam,
        "display_name": _one(idx, "displayName"),
        "distinguished_name": _one(idx, "distinguishedName"),
        "description": _one(idx, "description"),
        "members": members,
        "member_count": len(members),
        "is_privileged": is_priv,
        "admin_count": _int(idx, "adminCount"),
        "synced_at": datetime.now(timezone.utc),
    }


async def _sync_generic(session, model, key_field, rows_data) -> dict:
    created = updated = skipped = 0
    for data in rows_data:
        if not data:
            skipped += 1
            continue
        existing = (
            await session.execute(
                select(model).where(getattr(model, key_field) == data[key_field])
            )
        ).scalars().first()
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            updated += 1
        else:
            session.add(model(**data))
            created += 1
    await session.commit()
    return {"created": created, "updated": updated, "skipped": skipped}


async def sync_computers(session: AsyncSession, usn_filter: str | None = None) -> dict:
    ldap = ReadOnlyLDAP(settings)
    base = settings.ad_computers_search_base or settings.ad_base_dn
    entries = ldap.search(base, _with_usn(COMPUTER_FILTER, usn_filter), COMPUTER_ATTRS)
    result = await _sync_generic(
        session, ADComputer, "object_sid", [map_computer(e) for e in entries]
    )
    result["total"] = len(entries)
    logger.info("AD sync (computadores) concluído: %s", result)
    return result


async def sync_groups(session: AsyncSession, usn_filter: str | None = None) -> dict:
    ldap = ReadOnlyLDAP(settings)
    base = settings.ad_groups_search_base or settings.ad_base_dn
    entries = ldap.search(base, _with_usn(GROUP_FILTER, usn_filter), GROUP_ATTRS)
    result = await _sync_generic(
        session, ADGroup, "object_sid", [map_group(e) for e in entries]
    )
    result["total"] = len(entries)
    logger.info("AD sync (grupos) concluído: %s", result)
    return result


async def sync_all(session: AsyncSession, force_full: bool = False) -> dict:
    """Sincroniza usuários, grupos e computadores.

    Modo incremental (AD_SYNC_MODE=incremental): usa o watermark uSNChanged do
    último sync para buscar apenas objetos alterados. O primeiro sync (sem
    checkpoint) e ``force_full`` fazem sync completo.
    """
    from datetime import datetime, timezone

    from sqlalchemy import select as _select

    from app.models.ops import ADSyncCheckpoint

    source = settings.ad_base_dn
    ldap = ReadOnlyLDAP(settings)

    checkpoint = (
        await session.execute(_select(ADSyncCheckpoint).where(ADSyncCheckpoint.source == source))
    ).scalars().first()

    incremental = (
        not force_full
        and settings.ad_sync_mode == "incremental"
        and settings.ad_sync_usn_changed_enabled
        and checkpoint is not None
        and checkpoint.highest_usn > 0
    )

    # captura o USN corrente ANTES de ler (garante não perder alterações concorrentes)
    current_usn = ldap.get_highest_committed_usn()
    usn_filter = f"(uSNChanged>={checkpoint.highest_usn})" if incremental else None

    if incremental:
        logger.info("AD sync incremental desde uSNChanged=%s", checkpoint.highest_usn)
    else:
        logger.info("AD sync completo (mode=%s, force_full=%s)", settings.ad_sync_mode, force_full)

    users = await sync_users(session, usn_filter)
    groups = await sync_groups(session, usn_filter)
    computers = await sync_computers(session, usn_filter)

    now = datetime.now(timezone.utc)
    if checkpoint:
        checkpoint.highest_usn = max(current_usn, checkpoint.highest_usn)
        checkpoint.updated_at = now
        if incremental:
            checkpoint.last_incremental_at = now
        else:
            checkpoint.last_full_sync_at = now
    else:
        session.add(ADSyncCheckpoint(
            source=source, highest_usn=current_usn,
            last_full_sync_at=now, updated_at=now,
        ))
    await session.commit()

    # invalida caches derivados do inventário (busca/score/dashboard)
    try:
        from app.core.cache import invalidate

        for ns in ("search", "score", "dashboard", "entity"):
            await invalidate(ns)
    except Exception:  # noqa: BLE001
        pass

    return {
        "mode": "incremental" if incremental else "full",
        "highest_usn": current_usn,
        "users": users, "groups": groups, "computers": computers,
    }
