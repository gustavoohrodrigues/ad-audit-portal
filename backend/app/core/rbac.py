"""Resolução de RBAC a partir dos grupos do Active Directory."""
from __future__ import annotations

import re

from app.config import get_settings
from app.models.enums import ROLE_RANK, Role

settings = get_settings()

# Extrai o CN de um DN de grupo (memberOf retorna DNs completos).
_CN_RE = re.compile(r"^CN=([^,]+)", re.IGNORECASE)


def _group_names(group_dns: list[str]) -> set[str]:
    names: set[str] = set()
    for dn in group_dns:
        m = _CN_RE.match(dn.strip())
        names.add((m.group(1) if m else dn).strip().lower())
    return names


def resolve_roles(group_dns: list[str]) -> list[str]:
    """Mapeia grupos AD -> roles da aplicação (conforme .env)."""
    mapping = settings.role_group_map  # nome_grupo_lower -> role
    present = _group_names(group_dns)
    roles = {role for gname, role in mapping.items() if gname in present}
    return sorted(roles, key=lambda r: ROLE_RANK.get(r, 0), reverse=True)


def highest_role(roles: list[str]) -> str | None:
    if not roles:
        return None
    return max(roles, key=lambda r: ROLE_RANK.get(r, 0))


# Capacidades por role (usado em checagens finas).
CAPABILITIES: dict[str, set[str]] = {
    Role.viewer: {"dashboard:read", "user:read_basic"},
    Role.helpdesk: {
        "dashboard:read",
        "user:read_basic",
        "lockout:read",
        "password_event:read",
        "note:write",
        "ticket:link",
    },
    Role.security_analyst: {
        "dashboard:read",
        "user:read_basic",
        "user:read_full",
        "lockout:read",
        "password_event:read",
        "note:write",
        "ticket:link",
        "event:raw_read",
        "report:export",
        "investigation:manage",
        "critical:read",
    },
    Role.administrator: {"*"},
}


def has_capability(roles: list[str], capability: str) -> bool:
    for role in roles:
        caps = CAPABILITIES.get(role, set())
        if "*" in caps or capability in caps:
            return True
    return False
