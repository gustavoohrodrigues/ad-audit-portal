"""Testes das funcionalidades das Fases 1 e 2 (partes puras, sem banco)."""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
os.environ.setdefault("AD_ENABLED", "false")

from app.models.directory import ADUser  # noqa: E402
from app.services import messaging  # noqa: E402
from app.services.detections import _risk  # noqa: E402
from app.services.posture import score_from_counts  # noqa: E402


# ---------------- Score (posture) ----------------
def test_score_perfect_when_no_issues():
    r = score_from_counts({"total_users": 100})
    assert r["score"] == 100
    assert r["grade"] == "A"
    assert r["factors"] == []


def test_score_penalizes_password_not_required():
    r = score_from_counts({"total_users": 100, "password_not_required": 3})
    assert r["score"] == 80  # 3*10 capped em 20
    assert any("Password Not Required" in f["label"] for f in r["factors"])


def test_score_capped_at_zero():
    r = score_from_counts({
        "total_users": 100, "password_not_required": 50, "asrep": 50,
        "sid_history": 50, "delegation": 50, "never_expires": 500,
        "inactive": 500, "legacy_machines": 5000, "privileged": 90,
    })
    assert r["score"] == 0
    assert r["grade"] == "F"


def test_score_privilege_ratio_threshold():
    # 3% não penaliza; acima penaliza
    assert score_from_counts({"total_users": 100, "privileged": 3})["score"] == 100
    assert score_from_counts({"total_users": 100, "privileged": 10})["score"] < 100


# ---------------- Messaging ----------------
def test_messaging_sanitize_strips_control_chars():
    assert messaging.sanitize("ola\x00\x07mundo") == "olamundo"


def test_messaging_invalid_channel():
    r = messaging.deliver("telegram", "s", "b")
    assert r.ok is False
    assert "inv" in r.message.lower()


def test_messaging_correlation_id_present():
    r = messaging.deliver("teams", "s", "b")  # não configurado -> falha controlada
    assert r.correlation_id
    assert r.ok is False


# ---------------- Detections risk ----------------
def _user(**kw) -> ADUser:
    base = dict(object_sid="S-1-5-21-1-1-1-1", sam_account_name="svc")
    base.update(kw)
    return ADUser(**base)


def test_risk_privileged_and_old_password():
    u = _user(is_privileged=True, admin_count=1, password_never_expires=True,
              pwd_last_set=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=800))
    # base 45 (kerberoast) + 25 priv + 15 admincount + 10 neverexpire + 15 senha antiga
    assert _risk(u, 45) == 100


def test_risk_plain_account():
    u = _user(is_privileged=False)
    assert _risk(u, 45) == 45


# ---------------- Capacity helper ----------------
def test_capacity_human_bytes():
    from app.api.v1.endpoints.capacity import _human

    assert _human(0) == "0 B"
    assert _human(512) == "512.0 B"
    assert _human(1024) == "1.0 KB"
    assert _human(18 * 1024 * 1024).endswith("MB")
    assert _human(None) == "0 B"


# ---------------- Central de mensagens ----------------
def test_resolve_email_forces_domain():
    from app.api.v1.endpoints.broadcast import _resolve_email

    # domínio sempre forçado, independente do mail/UPN original
    assert _resolve_email(_user(sam_account_name="rafael.lopes")).endswith("@astra-sa.com")
    assert _resolve_email(_user(sam_account_name="x", mail="joao@empresa.local")) == "joao@astra-sa.com"
    assert _resolve_email(_user(sam_account_name="ana.silva")) == "ana.silva@astra-sa.com"


def test_google_chat_url_validation():
    from app.services.messaging import is_google_chat_url

    assert is_google_chat_url("https://chat.googleapis.com/v1/spaces/X/messages?key=k") is True
    assert is_google_chat_url("https://evil.example.com/webhook") is False
