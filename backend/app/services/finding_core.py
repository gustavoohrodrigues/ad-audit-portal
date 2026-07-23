"""Núcleo puro de findings: validação, fingerprint, mascaramento e risco.

Sem dependências de banco — facilita testes e reuso pelos adapters. Toda entrada
de scanner passa por ``coerce_finding`` (valida tipos, limita tamanhos, restringe
enums) antes de tocar o banco. Segredos NUNCA são armazenados em texto puro.
"""
from __future__ import annotations

import hashlib
from typing import Any

SEVERITIES = ("critical", "high", "medium", "low", "info", "unknown")
CATEGORIES = ("vulnerability", "misconfiguration", "secret", "hardening",
              "exposure", "compliance", "malware", "other")
ASSET_TYPES = ("image", "host", "repo", "container", "service", "dependency", "filesystem")
CONFIDENCE = ("high", "medium", "low")
STATUSES = ("open", "suppressed", "resolved")
REMEDIATION_STATES = ("none", "in_progress", "fixed", "wont_fix")

_SEV_BASE = {"critical": 90, "high": 70, "medium": 45, "low": 20, "info": 5, "unknown": 15}
_MAX = {"title": 300, "description": 4000, "remediation": 2500, "str": 512, "refs": 25}


def _clip(v: Any, n: int) -> str | None:
    if v is None:
        return None
    s = str(v).replace("\x00", "").strip()
    return s[:n] if s else None


def normalize_severity(v: Any) -> str:
    s = str(v or "").strip().lower()
    if s in ("critical", "crit"):
        return "critical"
    if s in ("high", "important"):
        return "high"
    if s in ("medium", "moderate", "warning", "warn"):
        return "medium"
    if s in ("low", "minor", "note", "info-low"):
        return "low"
    if s in ("info", "informational", "unknown", "none", "negligible"):
        return "info" if s != "unknown" and s != "none" else "unknown"
    return "unknown"


def mask_secret(value: Any) -> str:
    """Mascara um segredo, preservando só pistas mínimas para remediação."""
    s = str(value or "")
    if len(s) <= 6:
        return "******"
    return f"{s[:2]}{'*' * 8}{s[-2:]} (len={len(s)})"


def _band(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 65:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 15:
        return "low"
    return "info"


def compute_risk(f: dict[str, Any]) -> tuple[int, str]:
    """Score prático 0-100 combinando severidade + contexto (não só severidade)."""
    score = _SEV_BASE.get(f.get("severity", "unknown"), 15)
    if f.get("exploit_available"):
        score += 12
    if f.get("internet_exposed"):
        score += 10
    if f.get("privileged_context"):
        score += 8
    if f.get("fixed_version"):
        score += 5  # existe correção -> priorizar
    env = str(f.get("environment", "")).lower()
    if env in ("production", "prod", "prd"):
        score += 8
    conf = f.get("confidence", "medium")
    if conf == "low":
        score -= 10
    elif conf == "high":
        score += 3
    score = max(0, min(100, score))
    return score, _band(score)


def fingerprint(f: dict[str, Any]) -> str:
    """Chave estável de deduplicação/correlação entre execuções e fontes."""
    parts = [
        str(f.get("source_tool", "")),
        str(f.get("asset_type", "")),
        str(f.get("asset_name", "")),
        str(f.get("category", "")),
        str(f.get("cve") or f.get("title", "")),
        str(f.get("package_name") or ""),
        str(f.get("file_path") or f.get("config_path") or ""),
    ]
    return hashlib.sha256("|".join(parts).lower().encode("utf-8", "ignore")).hexdigest()[:40]


def coerce_finding(raw: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """Valida e normaliza um finding vindo de qualquer fonte. Sanitiza e limita."""
    d = {**(defaults or {}), **(raw or {})}

    sev = normalize_severity(d.get("severity"))
    category = str(d.get("category", "vulnerability")).lower()
    if category not in CATEGORIES:
        category = "other"
    asset_type = str(d.get("asset_type", "host")).lower()
    if asset_type not in ASSET_TYPES:
        asset_type = "host"
    conf = str(d.get("confidence", "medium")).lower()
    if conf not in CONFIDENCE:
        conf = "medium"

    refs = d.get("references") or []
    if isinstance(refs, str):
        refs = [refs]
    refs = [_clip(r, _MAX["str"]) for r in list(refs)[: _MAX["refs"]] if r]

    tags = d.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tags = [_clip(t, 64) for t in list(tags)[:30] if t]

    evidence = d.get("evidence") if isinstance(d.get("evidence"), dict) else {}
    # nunca deixa passar um campo de segredo cru na evidência
    for k in ("secret", "match", "raw", "value", "password", "token"):
        if k in evidence:
            evidence[k] = mask_secret(evidence[k])

    cvss = d.get("cvss")
    try:
        cvss = round(float(cvss), 1) if cvss is not None else None
        if cvss is not None and not (0.0 <= cvss <= 10.0):
            cvss = None
    except (TypeError, ValueError):
        cvss = None

    out = {
        "source_tool": _clip(d.get("source_tool", "manual"), 64) or "manual",
        "source_type": _clip(d.get("source_type"), 64),
        "category": category,
        "subcategory": _clip(d.get("subcategory"), 128),
        "asset_type": asset_type,
        "asset_id": _clip(d.get("asset_id"), _MAX["str"]),
        "asset_name": _clip(d.get("asset_name", "unknown"), _MAX["str"]) or "unknown",
        "environment": _clip(d.get("environment", "unknown"), 64) or "unknown",
        "host_name": _clip(d.get("host_name"), _MAX["str"]),
        "service_name": _clip(d.get("service_name"), _MAX["str"]),
        "severity": sev,
        "confidence": conf,
        "title": _clip(d.get("title", ""), _MAX["title"]) or "(sem título)",
        "description": _clip(d.get("description"), _MAX["description"]),
        "evidence": evidence,
        "remediation": _clip(d.get("remediation"), _MAX["remediation"]),
        "references": refs,
        "cve": _clip(d.get("cve"), 64),
        "cwe": _clip(d.get("cwe"), 64),
        "cvss": cvss,
        "package_name": _clip(d.get("package_name"), _MAX["str"]),
        "installed_version": _clip(d.get("installed_version"), 128),
        "fixed_version": _clip(d.get("fixed_version"), 128),
        "file_path": _clip(d.get("file_path"), _MAX["str"]),
        "config_path": _clip(d.get("config_path"), _MAX["str"]),
        "exploit_available": bool(d.get("exploit_available", False)),
        "internet_exposed": bool(d.get("internet_exposed", False)),
        "privileged_context": bool(d.get("privileged_context", False)),
        "tags": tags,
    }
    out["risk_score"], out["risk_band"] = compute_risk(out)
    out["fingerprint"] = fingerprint(out)
    return out
