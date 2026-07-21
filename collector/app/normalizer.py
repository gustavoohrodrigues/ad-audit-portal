"""Normalização de eventos do Windows Security Log para o modelo canônico.

Aceita tanto o formato XML do Windows Event (convertido para dict) quanto JSON
já estruturado (Winlogbeat/Wazuh/NXLog). Mapeia Event IDs para EventType e
extrai os campos relevantes, com tratamento especial para 4740 (bloqueio).

Regra de deduplicação (a jusante): (domain_controller, event_record_id, event_id).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Mapeamento Event ID -> (event_type, severity_base)
EVENT_ID_MAP: dict[int, str] = {
    4624: "successful_logon",
    4625: "failed_logon",
    4720: "user_created",
    4722: "account_enabled",
    4723: "password_change",
    4724: "password_reset",
    4725: "account_disabled",
    4726: "user_deleted",
    4728: "group_member_added",
    4732: "group_member_added",
    4756: "group_member_added",
    4729: "group_member_removed",
    4733: "group_member_removed",
    4757: "group_member_removed",
    4738: "account_changed",
    4740: "account_lockout",
    4767: "account_unlocked",
    4771: "kerberos_preauth_failed",
    4776: "ntlm_validation",
    4781: "account_renamed",
    5136: "ds_object_modified",
    5137: "ds_object_created",
    5141: "ds_object_deleted",
    4768: "kerberos_tgt_request",
    4769: "kerberos_service_ticket",
    4770: "kerberos_ticket_renewed",
    4773: "kerberos_service_ticket_failed",
    4648: "explicit_credential_logon",
    4672: "special_privileges_assigned",
    4697: "service_installed",
    7045: "service_installed",
}

# Grupos considerados privilegiados (também vem do .env no worker; aqui heurística)
PRIVILEGED_GROUP_HINTS = {
    "domain admins", "enterprise admins", "schema admins", "administrators",
    "account operators", "backup operators", "server operators", "print operators",
}


def _get(data: dict, *keys: str, default=None):
    """Busca a primeira chave presente (case-insensitive) no dict de EventData."""
    lower = {k.lower(): v for k, v in data.items()}
    for k in keys:
        if k.lower() in lower and lower[k.lower()] not in (None, "", "-"):
            return lower[k.lower()]
    return default


def _parse_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        v = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(v)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def normalize(raw: dict[str, Any], collector_source: str = "wef") -> dict[str, Any] | None:
    """Converte um evento bruto em um dict pronto para inserção.

    Retorna None se o Event ID não for de interesse.
    """
    # Estrutura esperada: {System:{EventID, Computer, TimeCreated, EventRecordID},
    #                      EventData:{...}} — ou campos planos (winlogbeat).
    system = raw.get("System") or raw.get("system") or {}
    event_data = raw.get("EventData") or raw.get("event_data") or {}

    # winlogbeat/flat fallback
    if not system and "winlog" in raw:
        winlog = raw["winlog"]
        system = {
            "EventID": winlog.get("event_id"),
            "Computer": winlog.get("computer_name"),
            "EventRecordID": winlog.get("record_id"),
        }
        event_data = winlog.get("event_data", {})

    try:
        event_id = int(_get(system, "EventID", "event_id") or raw.get("event_id") or 0)
    except (TypeError, ValueError):
        return None

    event_type = EVENT_ID_MAP.get(event_id)
    if not event_type:
        return None

    dc = str(
        _get(system, "Computer", "computer") or raw.get("computer") or "unknown"
    )
    event_time = _parse_time(
        _get(system, "TimeCreated", "time_created") or raw.get("@timestamp")
    )
    try:
        record_id = int(_get(system, "EventRecordID", "record_id") or 0) or None
    except (TypeError, ValueError):
        record_id = None

    # ---- campos por tipo ----
    target_user = _get(event_data, "TargetUserName", "target_user")
    target_sid = _get(event_data, "TargetSid", "TargetUserSid")
    actor_user = _get(event_data, "SubjectUserName")
    actor_sid = _get(event_data, "SubjectUserSid")
    caller = _get(event_data, "CallerComputerName", "WorkstationName", "Workstation")
    source_ip = _get(event_data, "IpAddress", "ClientAddress")
    logon_id = _get(event_data, "TargetLogonId", "SubjectLogonId")
    auth_pkg = _get(event_data, "AuthenticationPackageName", "LmPackageName")
    status_code = _get(event_data, "Status", "SubStatus")
    failure = _get(event_data, "FailureReason", "Status")
    group_name = _get(event_data, "TargetUserName") if "group" in event_type else None

    is_priv = False
    if event_type in ("group_member_added", "group_member_removed"):
        gname = str(_get(event_data, "TargetUserName", "GroupName") or "").lower()
        is_priv = any(h in gname for h in PRIVILEGED_GROUP_HINTS)

    normalized = {
        "event_time_utc": event_time,
        "event_record_id": record_id,
        "event_id": event_id,
        "event_type": event_type,
        "domain_controller": dc,
        "domain": _get(event_data, "TargetDomainName", "SubjectDomainName"),
        "target_username": str(target_user) if target_user else None,
        "target_upn": _get(event_data, "TargetUserPrincipalName"),
        "target_sid": str(target_sid) if target_sid else None,
        "actor_username": str(actor_user) if actor_user else None,
        "actor_sid": str(actor_sid) if actor_sid else None,
        "actor_domain": _get(event_data, "SubjectDomainName"),
        "caller_computer": str(caller).strip("\\") if caller else None,
        "source_ip": _clean_ip(source_ip),
        "logon_id": str(logon_id) if logon_id else None,
        "workstation_name": _get(event_data, "WorkstationName"),
        "authentication_package": str(auth_pkg) if auth_pkg else None,
        "status_code": str(status_code) if status_code else None,
        "failure_reason": str(failure) if failure else None,
        "collector_source": collector_source,
        "is_privileged_target": is_priv,
        "raw_event_json": raw,
    }
    return normalized


def _clean_ip(value: Any) -> str | None:
    if not value or value in ("-", "::1", "127.0.0.1"):
        return None
    s = str(value)
    return s[7:] if s.startswith("::ffff:") else s
