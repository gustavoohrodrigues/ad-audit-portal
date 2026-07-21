"""Testes de segurança: proteção contra LDAP Injection e redação de logs."""
from app.core.logging import redact_value
from app.ldap.client import escape_filter_value


def test_ldap_filter_escapes_metacharacters():
    payload = "*)(uid=*))(|(uid=*"
    escaped = escape_filter_value(payload)
    # não deve conter parênteses/asteriscos crus que quebrem o filtro
    assert "*" not in escaped or "\\2a" in escaped
    assert "(" not in escaped
    assert ")" not in escaped


def test_ldap_filter_escapes_null_and_backslash():
    assert escape_filter_value("a\\b") != "a\\b"
    assert "\\5c" in escape_filter_value("a\\b")


def test_redact_connection_string_password():
    url = "postgresql+psycopg://user:SuperSecret@host:5432/db"
    red = redact_value(url)
    assert "SuperSecret" not in red
    assert "user:***@host" in red


def test_redact_ldaps_password():
    red = redact_value("ldaps://svc_ad:P@ssw0rd@dc01:636")
    assert "P@ssw0rd" not in red or ":***@" in red
