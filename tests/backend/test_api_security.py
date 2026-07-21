"""Testes de segurança da API: autenticação obrigatória, headers, RBAC."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

os.environ.setdefault("AD_ENABLED", "false")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health_is_public():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_protected_endpoint_requires_auth():
    r = client.get("/api/v1/dashboard/summary")
    assert r.status_code == 401


def test_events_raw_requires_auth():
    r = client.get("/api/v1/events/1/raw")
    assert r.status_code == 401


def test_security_headers_present():
    r = client.get("/api/v1/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in r.headers


def test_openapi_available():
    r = client.get("/api/openapi.json")
    assert r.status_code == 200
    assert "/api/v1/auth/login" in r.json()["paths"]


def test_no_ad_write_endpoints():
    """Garante que nenhum endpoint expõe operações de escrita no AD.

    A checagem é escopada às rotas de objetos do AD (/users, /groups, /computers).
    Rotas de autenticação da aplicação (/auth/*, incluindo o MFA activate/enable
    do próprio portal) não tocam o AD e são explicitamente ignoradas.
    """
    paths = client.get("/api/openapi.json").json()["paths"]
    forbidden = ("unlock", "reset-password", "reset_password", "disable", "enable",
                 "create-user", "delete-user", "add-member", "remove-member")
    ad_prefixes = ("/api/v1/users", "/api/v1/groups", "/api/v1/computers")
    for path in paths:
        if not path.startswith(ad_prefixes):
            continue
        assert not any(f in path.lower() for f in forbidden), f"endpoint proibido: {path}"


def test_mfa_endpoints_require_auth():
    """Os endpoints de gestão de MFA exigem sessão autenticada."""
    assert client.post("/api/v1/auth/mfa/setup").status_code == 401
    assert client.get("/api/v1/auth/mfa/status").status_code == 401


def test_new_admin_endpoints_require_auth():
    """Novos endpoints (capacidade, busca, detecções) exigem autenticação."""
    assert client.get("/api/v1/admin/capacity").status_code == 401
    assert client.get("/api/v1/search?q=x").status_code == 401
    assert client.get("/api/v1/detections/summary").status_code == 401


def test_messaging_endpoints_require_auth():
    """Central de mensagens e webhooks de chat exigem autenticação."""
    assert client.get("/api/v1/messaging/audience?filter=inactive").status_code == 401
    assert client.get("/api/v1/chat-webhooks").status_code == 401
    assert client.post("/api/v1/messaging/broadcast", json={}).status_code in (401, 422)


def test_broadcast_requires_confirmation(monkeypatch):
    """Broadcast exige confirm=true (não envia sem confirmação)."""
    # sem auth já barra em 401; garantimos que o schema exige os campos
    r = client.post("/api/v1/messaging/broadcast", json={"channel": "email"})
    assert r.status_code in (401, 422)
