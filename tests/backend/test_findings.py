"""Testes de segurança da camada de findings (Security Ops).

Cobre: mascaramento de segredos (nunca vaza), deduplicação estável, risco,
validação/limitação de entrada, rejeição de payload malformado e enforcement
de autenticação nas rotas privilegiadas.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
os.environ.setdefault("AD_ENABLED", "false")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import finding_adapters as ad  # noqa: E402
from app.services import finding_core as core  # noqa: E402

client = TestClient(app)


TRIVY = {
    "ArtifactName": "app:1.0", "ArtifactType": "container_image",
    "Results": [
        {"Target": "app", "Class": "os-pkgs", "Type": "debian", "Vulnerabilities": [
            {"VulnerabilityID": "CVE-2024-1", "PkgName": "openssl", "InstalledVersion": "1",
             "FixedVersion": "2", "Severity": "CRITICAL", "Title": "RCE",
             "CVSS": {"nvd": {"V3Score": 9.8}}}]},
        {"Target": ".env", "Class": "secret", "Secrets": [
            {"RuleID": "aws-key", "Severity": "CRITICAL", "Title": "AWS",
             "StartLine": 3, "Match": "AKIAIOSFODNN7EXAMPLE_super_secret"}]},
    ],
}


def test_secret_is_masked_and_never_leaks():
    findings = ad.parse_trivy(TRIVY, {"environment": "prod"})
    secret = [f for f in findings if f["category"] == "secret"][0]
    blob = str(secret)
    assert "AKIAIOSFODNN7EXAMPLE_super_secret" not in blob
    assert "********" in str(secret["evidence"]["match_masked"])


def test_mask_secret_helper_never_returns_raw():
    raw = "supersecrettoken12345"
    masked = core.mask_secret(raw)
    assert raw not in masked
    assert masked.startswith("su") and "****" in masked


def test_fingerprint_is_stable_for_dedup():
    a = ad.parse_trivy(TRIVY, {"environment": "prod"})
    b = ad.parse_trivy(TRIVY, {"environment": "prod"})
    assert [f["fingerprint"] for f in a] == [f["fingerprint"] for f in b]


def test_risk_combines_context_not_only_severity():
    low_ctx = core.coerce_finding({"severity": "high", "confidence": "low"})
    prod_exposed = core.coerce_finding({
        "severity": "high", "confidence": "high", "internet_exposed": True,
        "exploit_available": True, "environment": "production", "fixed_version": "2",
    })
    assert prod_exposed["risk_score"] > low_ctx["risk_score"]
    assert prod_exposed["risk_band"] in ("high", "critical")


def test_coerce_limits_and_sanitizes():
    f = core.coerce_finding({"title": "x" * 5000, "severity": "BOGUS", "cvss": 99})
    assert len(f["title"]) <= 300
    assert f["severity"] == "unknown"
    assert f["cvss"] is None  # cvss inválido é descartado


def test_malformed_scanner_input_is_rejected_safely():
    import pytest
    with pytest.raises(ValueError):
        ad.parse_trivy("not-a-dict", {})
    with pytest.raises(ValueError):
        ad.parse_normalized({"not": "a list"}, {})


def test_findings_routes_require_auth():
    assert client.get("/api/v1/security/findings").status_code == 401
    assert client.get("/api/v1/security/findings/overview").status_code == 401
    assert client.post("/api/v1/security/findings/ingest", json={"format": "trivy", "content": {}}).status_code == 401


def test_grype_adapter_parses_and_enriches_cve():
    grype = {"source": {"type": "image", "target": {"userInput": "api:1"}},
             "matches": [{"vulnerability": {"id": "CVE-2024-6387", "severity": "Critical",
                          "fix": {"versions": ["9.8p1"]}, "cvss": [{"metrics": {"baseScore": 8.1}}]},
                          "artifact": {"name": "openssh", "version": "9.6p1", "type": "deb"}}]}
    out = ad.parse_grype(grype, {})
    assert out and out[0]["cve"] == "CVE-2024-6387" and out[0]["fixed_version"] == "9.8p1"
    # enriquecimento de referências NVD/MITRE (sem fetch externo)
    assert any("nvd.nist.gov" in r for r in out[0]["references"])


def test_gitleaks_never_leaks_secret():
    gl = [{"RuleID": "aws", "File": "a.tf", "StartLine": 1,
           "Secret": "AKIAIOSFODNN7EXAMPLE", "Match": "key=AKIAIOSFODNN7EXAMPLE"}]
    out = ad.parse_gitleaks(gl, {})
    assert "AKIAIOSFODNN7EXAMPLE" not in str(out)
    assert out[0]["category"] == "secret"


def test_lynis_text_report_becomes_hardening_findings():
    report = ("hostname=srv1\nhardening_index=61\n"
              "warning[]=SSH-7408|Root login permitted|PermitRootLogin yes|Set no\n"
              "suggestion[]=FIRE-4513|No firewall|-|Enable ufw\n")
    out = ad.parse_lynis(report, {})
    assert len(out) == 2
    assert all(f["category"] == "hardening" and f["asset_type"] == "host" for f in out)
    assert any(f["severity"] == "high" for f in out)


def test_unsupported_format_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        ad.run_adapter("nao_existe", {}, {})
