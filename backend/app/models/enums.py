"""Enums de domínio compartilhados por modelos e schemas."""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    viewer = "viewer"
    helpdesk = "helpdesk"
    security_analyst = "security_analyst"
    administrator = "administrator"


# Ordem de privilégio — usado para resolver a maior role de um usuário.
ROLE_RANK: dict[str, int] = {
    Role.viewer: 1,
    Role.helpdesk: 2,
    Role.security_analyst: 3,
    Role.administrator: 4,
}


class Severity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class EventType(str, Enum):
    successful_logon = "successful_logon"
    failed_logon = "failed_logon"
    user_created = "user_created"
    account_enabled = "account_enabled"
    password_change = "password_change"          # 4723 — próprio usuário
    password_reset = "password_reset"            # 4724 — por operador
    account_disabled = "account_disabled"
    user_deleted = "user_deleted"
    group_member_added = "group_member_added"
    group_member_removed = "group_member_removed"
    account_changed = "account_changed"
    account_lockout = "account_lockout"          # 4740
    account_unlocked = "account_unlocked"        # 4767
    kerberos_preauth_failed = "kerberos_preauth_failed"  # 4771
    ntlm_validation = "ntlm_validation"          # 4776
    account_renamed = "account_renamed"
    ds_object_modified = "ds_object_modified"    # 5136
    ds_object_created = "ds_object_created"      # 5137
    ds_object_deleted = "ds_object_deleted"      # 5141
    kerberos_tgt_request = "kerberos_tgt_request"                # 4768
    kerberos_service_ticket = "kerberos_service_ticket"          # 4769
    kerberos_ticket_renewed = "kerberos_ticket_renewed"          # 4770
    kerberos_service_ticket_failed = "kerberos_service_ticket_failed"  # 4773
    explicit_credential_logon = "explicit_credential_logon"      # 4648
    special_privileges_assigned = "special_privileges_assigned"  # 4672
    service_installed = "service_installed"                      # 4697 / 7045
    other = "other"


class InvestigationStatus(str, Enum):
    new = "new"
    in_analysis = "in_analysis"
    mitigated = "mitigated"
    false_positive = "false_positive"
    closed = "closed"


class AlertStatus(str, Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"
    suppressed = "suppressed"


class SourceStatus(str, Enum):
    healthy = "healthy"
    degraded = "degraded"
    down = "down"
    unknown = "unknown"
