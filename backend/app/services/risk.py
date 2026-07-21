"""Cálculo de pontuação de risco (0–100) para eventos e contas.

Regras principais (configuráveis via .env):
- Bloqueios recorrentes aumentam o risco.
- Alteração de grupo privilegiado -> crítico.
- Reset de senha de conta privilegiada -> alto.
- Criação de conta administrativa -> crítico.
- Alteração de SPN / SIDHistory / delegação -> alto.
- Eventos fora do horário comercial aumentam pontuação.
- Ações em contas ou OUs críticas aumentam pontuação.
"""
from __future__ import annotations

from datetime import datetime

from app.config import get_settings
from app.models.enums import EventType, Severity

settings = get_settings()

# Score base por tipo de evento.
_BASE: dict[EventType, int] = {
    EventType.account_lockout: 30,
    EventType.failed_logon: 10,
    EventType.password_reset: 40,
    EventType.password_change: 15,
    EventType.account_changed: 25,
    EventType.user_created: 35,
    EventType.user_deleted: 45,
    EventType.account_disabled: 20,
    EventType.account_enabled: 25,
    EventType.group_member_added: 30,
    EventType.group_member_removed: 30,
    EventType.account_renamed: 25,
    EventType.ds_object_modified: 20,
    EventType.ds_object_deleted: 45,
    EventType.kerberos_preauth_failed: 10,
    EventType.ntlm_validation: 8,
    EventType.successful_logon: 0,
    EventType.other: 5,
}


def is_outside_business_hours(dt: datetime) -> bool:
    hour = dt.hour
    if dt.weekday() >= 5:  # sábado/domingo
        return True
    return hour < settings.business_hours_start or hour >= settings.business_hours_end


def score_event(
    *,
    event_type: EventType,
    event_time: datetime,
    is_privileged_target: bool = False,
    is_critical_account: bool = False,
    privileged_group_change: bool = False,
    spn_or_delegation_change: bool = False,
    recurring_lockouts: int = 0,
) -> tuple[int, Severity]:
    score = _BASE.get(event_type, 5)

    if privileged_group_change:
        score += 55
    if spn_or_delegation_change:
        score += 45
    if event_type == EventType.password_reset and is_privileged_target:
        score += 40
    if event_type == EventType.user_created and is_privileged_target:
        score += 55
    if is_privileged_target:
        score += 20
    if is_critical_account:
        score += 25
    if recurring_lockouts >= settings.recurring_lockout_threshold:
        score += 20 + min(recurring_lockouts, 10) * 2
    if is_outside_business_hours(event_time):
        score += 15

    score = max(0, min(100, score))
    return score, severity_for(score)


def severity_for(score: int) -> Severity:
    if score >= settings.risk_alert_threshold_critical:
        return Severity.critical
    if score >= settings.risk_alert_threshold_high:
        return Severity.high
    if score >= settings.risk_alert_threshold_medium:
        return Severity.medium
    if score > 0:
        return Severity.low
    return Severity.info
