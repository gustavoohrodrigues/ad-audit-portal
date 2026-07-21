"""Conversão de atributos do Active Directory para tipos legíveis.

pwdLastSet, accountExpires, lockoutTime, lastLogonTimestamp etc. são
armazenados como FILETIME (100-ns desde 1601-01-01). Convertidos para
datetime UTC. objectSID e objectGUID convertidos para formato string.
"""
from __future__ import annotations

import struct
import uuid
from datetime import datetime, timedelta, timezone

# Epoch do Windows FILETIME
_FILETIME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)
# accountExpires "never" = 0 ou 0x7FFFFFFFFFFFFFFF
_NEVER = 0x7FFFFFFFFFFFFFFF

# Flags do userAccountControl
UAC_ACCOUNTDISABLE = 0x0002
UAC_LOCKOUT = 0x0010
UAC_PASSWD_NOTREQD = 0x0020
UAC_DONT_EXPIRE_PASSWORD = 0x10000
UAC_TRUSTED_FOR_DELEGATION = 0x80000
UAC_DONT_REQ_PREAUTH = 0x400000  # AS-REP roasting
UAC_PASSWORD_EXPIRED = 0x800000
UAC_TRUSTED_TO_AUTH_FOR_DELEGATION = 0x1000000


def filetime_to_datetime(value: int | str | None) -> datetime | None:
    """Converte FILETIME (100-ns desde 1601) para datetime UTC. None se 'never'."""
    if value is None:
        return None
    try:
        ival = int(value)
    except (TypeError, ValueError):
        return None
    if ival in (0, _NEVER):
        return None
    try:
        return _FILETIME_EPOCH + timedelta(microseconds=ival / 10)
    except (OverflowError, ValueError):
        return None


def sid_to_string(raw: bytes | str | None) -> str | None:
    """Converte objectSID binário para formato S-1-5-21-..."""
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw  # já em formato string (ldap3 pode retornar assim)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) < 8:
        return None
    revision = raw[0]
    sub_auth_count = raw[1]
    authority = int.from_bytes(raw[2:8], byteorder="big")
    sid = f"S-{revision}-{authority}"
    for i in range(sub_auth_count):
        off = 8 + i * 4
        sub = struct.unpack("<I", raw[off : off + 4])[0]
        sid += f"-{sub}"
    return sid


def guid_to_string(raw: bytes | str | None) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (bytes, bytearray)) and len(raw) == 16:
        return str(uuid.UUID(bytes_le=bytes(raw)))
    return None


def parse_uac(uac: int | str | None) -> dict[str, bool]:
    """Interpreta o userAccountControl em flags booleanas."""
    if uac is None:
        return {}
    try:
        v = int(uac)
    except (TypeError, ValueError):
        return {}
    return {
        "is_disabled": bool(v & UAC_ACCOUNTDISABLE),
        "is_locked": bool(v & UAC_LOCKOUT),
        "password_not_required": bool(v & UAC_PASSWD_NOTREQD),
        "password_never_expires": bool(v & UAC_DONT_EXPIRE_PASSWORD),
        "password_expired": bool(v & UAC_PASSWORD_EXPIRED),
        "dont_require_preauth": bool(v & UAC_DONT_REQ_PREAUTH),
        "trusted_for_delegation": bool(v & UAC_TRUSTED_FOR_DELEGATION),
        "trusted_to_auth_for_delegation": bool(
            v & UAC_TRUSTED_TO_AUTH_FOR_DELEGATION
        ),
    }
