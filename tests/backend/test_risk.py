"""Testes do motor de risco."""
from datetime import datetime, timezone

from app.models.enums import EventType, Severity
from app.services.risk import is_outside_business_hours, score_event, severity_for


def _dt(hour: int, weekday_offset: int = 0):
    # 2026-07-20 é uma segunda-feira
    from datetime import timedelta

    base = datetime(2026, 7, 20, hour, 0, tzinfo=timezone.utc)
    return base + timedelta(days=weekday_offset)


def test_priv_group_change_is_critical():
    score, sev = score_event(
        event_type=EventType.group_member_added,
        event_time=_dt(10),
        is_privileged_target=True,
        privileged_group_change=True,
    )
    assert score >= 90
    assert sev == Severity.critical


def test_privileged_password_reset_is_high():
    score, sev = score_event(
        event_type=EventType.password_reset,
        event_time=_dt(10),
        is_privileged_target=True,
    )
    assert sev in (Severity.high, Severity.critical)


def test_successful_logon_low_risk():
    score, sev = score_event(event_type=EventType.successful_logon, event_time=_dt(10))
    assert score < 50


def test_outside_business_hours_adds_risk():
    day = score_event(event_type=EventType.account_changed, event_time=_dt(10))[0]
    night = score_event(event_type=EventType.account_changed, event_time=_dt(23))[0]
    assert night > day


def test_weekend_is_outside_hours():
    assert is_outside_business_hours(_dt(10, weekday_offset=5)) is True  # sábado


def test_severity_thresholds():
    assert severity_for(95) == Severity.critical
    assert severity_for(80) == Severity.high
    assert severity_for(60) == Severity.medium
    assert severity_for(10) == Severity.low
    assert severity_for(0) == Severity.info


def test_score_capped_at_100():
    score, _ = score_event(
        event_type=EventType.user_created,
        event_time=_dt(23, weekday_offset=6),
        is_privileged_target=True,
        is_critical_account=True,
        privileged_group_change=True,
        spn_or_delegation_change=True,
        recurring_lockouts=10,
    )
    assert score == 100
