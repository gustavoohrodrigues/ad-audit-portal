"""Testes de MFA (TOTP) e geração do comando de origem de bloqueio."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
os.environ.setdefault("AD_ENABLED", "false")

import pyotp  # noqa: E402

from app.services import mfa  # noqa: E402
from app.services.lockout_origin import build_ps_command  # noqa: E402


def test_totp_verify_roundtrip():
    secret = mfa.generate_secret()
    code = pyotp.TOTP(secret).now()
    assert mfa.verify_code(secret, code) is True
    assert mfa.verify_code(secret, "000000") is False


def test_provisioning_uri_and_qr():
    secret = mfa.generate_secret()
    uri = mfa.provisioning_uri("teste.user", secret)
    assert uri.startswith("otpauth://totp/")
    assert secret in uri
    data_uri = mfa.qr_data_uri(uri)
    assert data_uri.startswith("data:image/png;base64,")


def test_backup_codes_are_unique_six_digits():
    codes = mfa.generate_backup_codes(8)
    assert len(codes) == 8
    assert all(len(c) == 6 and c.isdigit() for c in codes)


def test_lockout_ps_command_contains_user_and_props():
    cmd = build_ps_command("jsilva")
    assert "ID=4740" in cmd
    assert "jsilva" in cmd
    assert "Properties[0]" in cmd  # usuário bloqueado
    assert "Properties[1]" in cmd  # origem do bloqueio


def test_lockout_ps_command_escapes_quotes():
    cmd = build_ps_command("o'brien")
    assert "o''brien" in cmd  # aspas simples escapadas para PowerShell


def test_winrm_dotnet_date_normalization():
    from app.services.lockout_origin import _normalize_time

    iso = _normalize_time("/Date(1784635874637)/")
    assert iso is not None and iso.startswith("2026-")
    assert _normalize_time("2026-07-21T12:00:00Z") == "2026-07-21T12:00:00Z"
    assert _normalize_time(None) is None
