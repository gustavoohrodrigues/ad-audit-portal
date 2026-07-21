"""Pontuação de risco (0–100) — versão do worker (sem dependência do backend)."""
from __future__ import annotations

from datetime import datetime

from app.config import config

_BASE = {
    "account_lockout": 30,
    "failed_logon": 10,
    "password_reset": 40,
    "password_change": 15,
    "account_changed": 25,
    "user_created": 35,
    "user_deleted": 45,
    "account_disabled": 20,
    "account_enabled": 25,
    "group_member_added": 30,
    "group_member_removed": 30,
    "account_renamed": 25,
    "ds_object_modified": 20,
    "ds_object_deleted": 45,
    "kerberos_preauth_failed": 10,
    "ntlm_validation": 8,
    "successful_logon": 0,
    "other": 5,
}


def outside_business_hours(dt: datetime) -> bool:
    if dt.weekday() >= 5:
        return True
    return dt.hour < config.business_start or dt.hour >= config.business_end


def severity_for(score: int) -> str:
    if score >= config.th_critical:
        return "critical"
    if score >= config.th_high:
        return "high"
    if score >= config.th_medium:
        return "medium"
    return "low" if score > 0 else "info"


def score_event(
    event_type: str,
    event_time: datetime,
    is_privileged_target: bool = False,
    is_critical_account: bool = False,
    privileged_group_change: bool = False,
    spn_or_delegation_change: bool = False,
    recurring_lockouts: int = 0,
) -> tuple[int, str]:
    score = _BASE.get(event_type, 5)
    if privileged_group_change:
        score += 55
    if spn_or_delegation_change:
        score += 45
    if event_type == "password_reset" and is_privileged_target:
        score += 40
    if event_type == "user_created" and is_privileged_target:
        score += 55
    if is_privileged_target:
        score += 20
    if is_critical_account:
        score += 25
    if recurring_lockouts >= config.recurring_lockout_threshold:
        score += 20 + min(recurring_lockouts, 10) * 2
    if outside_business_hours(event_time):
        score += 15
    score = max(0, min(100, score))
    return score, severity_for(score)
