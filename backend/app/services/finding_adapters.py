"""Adapters de ingestão: convertem a saída de scanners no modelo canônico.

Cada adapter é PURO (sem DB) e retorna uma lista de findings já validados por
``coerce_finding``. Nunca executa comando/subprocess — só faz parsing seguro de
dados já fornecidos (upload/import). Isso impede que a ingestão vire caminho de
RCE. Segredos são mascarados no adapter (não chegam crus ao banco).
"""
from __future__ import annotations

from typing import Any

from app.services.finding_core import coerce_finding, mask_secret

# Limite defensivo por lote (anti-DoS). Ajustável na camada de API.
MAX_FINDINGS = 20000


def _cvss_score(cvss: Any) -> float | None:
    """Extrai o maior V3Score de um bloco CVSS do Trivy."""
    if not isinstance(cvss, dict):
        return None
    best = None
    for vendor in cvss.values():
        if isinstance(vendor, dict):
            v = vendor.get("V3Score") or vendor.get("V2Score")
            try:
                fv = float(v)
                best = fv if best is None else max(best, fv)
            except (TypeError, ValueError):
                continue
    return best


def parse_trivy(content: dict[str, Any], meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Parser do JSON do Trivy (vuln OS/deps, segredos e misconfig; imagem/fs)."""
    if not isinstance(content, dict):
        raise ValueError("JSON do Trivy inválido (esperado objeto).")
    artifact = str(content.get("ArtifactName") or meta.get("asset_name") or "unknown")
    art_type = str(content.get("ArtifactType") or "").lower()
    asset_type = "image" if "image" in art_type else ("repo" if "repo" in art_type else "filesystem")
    env = meta.get("environment", "unknown")
    base = {"source_tool": "trivy", "asset_name": artifact, "asset_type": asset_type,
            "environment": env}

    out: list[dict[str, Any]] = []
    results = content.get("Results")
    if not isinstance(results, list):
        return out

    for res in results:
        if not isinstance(res, dict):
            continue
        target = str(res.get("Target") or "")
        klass = str(res.get("Class") or "")
        rtype = str(res.get("Type") or "")

        for v in (res.get("Vulnerabilities") or []):
            if not isinstance(v, dict):
                continue
            refs = []
            if v.get("PrimaryURL"):
                refs.append(v["PrimaryURL"])
            refs += list(v.get("References") or [])
            cwe = (v.get("CweIDs") or [None])[0]
            out.append(coerce_finding({
                "source_type": "dependency" if klass == "lang-pkgs" else "os",
                "category": "vulnerability", "subcategory": rtype or klass,
                "title": v.get("Title") or v.get("VulnerabilityID") or "Vulnerabilidade",
                "description": v.get("Description"),
                "severity": v.get("Severity"),
                "cve": v.get("VulnerabilityID"), "cwe": cwe,
                "cvss": _cvss_score(v.get("CVSS")),
                "package_name": v.get("PkgName"),
                "installed_version": v.get("InstalledVersion"),
                "fixed_version": v.get("FixedVersion"),
                "file_path": target or v.get("PkgPath"),
                "references": refs,
                "remediation": (f"Atualizar {v.get('PkgName')} para {v.get('FixedVersion')}"
                                if v.get("FixedVersion") else None),
            }, base))

        for m in (res.get("Misconfigurations") or []):
            if not isinstance(m, dict) or str(m.get("Status", "FAIL")).upper() != "FAIL":
                continue
            refs = ([m["PrimaryURL"]] if m.get("PrimaryURL") else []) + list(m.get("References") or [])
            out.append(coerce_finding({
                "source_type": "config", "category": "misconfiguration",
                "subcategory": m.get("Type"),
                "title": m.get("Title") or m.get("ID") or "Misconfiguração",
                "description": m.get("Description"),
                "severity": m.get("Severity"),
                "remediation": m.get("Resolution"),
                "config_path": target, "cve": m.get("ID"),
                "references": refs,
                "evidence": {"message": m.get("Message")} if m.get("Message") else {},
            }, base))

        for s in (res.get("Secrets") or []):
            if not isinstance(s, dict):
                continue
            out.append(coerce_finding({
                "source_type": "secret", "category": "secret", "confidence": "high",
                "subcategory": s.get("Category"),
                "title": s.get("Title") or s.get("RuleID") or "Segredo exposto",
                "severity": s.get("Severity") or "high",
                "file_path": target,
                # o segredo em si é MASCARADO — nunca armazenado cru
                "evidence": {
                    "rule": s.get("RuleID"),
                    "start_line": s.get("StartLine"),
                    "match_masked": mask_secret(s.get("Match")),
                },
                "remediation": "Remover o segredo do artefato e rotacioná-lo imediatamente.",
            }, base))

        if len(out) > MAX_FINDINGS:
            raise ValueError(f"Lote excede o limite de {MAX_FINDINGS} findings.")
    return out


def parse_normalized(items: Any, meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Import normalizado genérico (Lynis/coletor/osquery/etc. já mapeados)."""
    if not isinstance(items, list):
        raise ValueError("Import normalizado espera uma lista de findings.")
    if len(items) > MAX_FINDINGS:
        raise ValueError(f"Lote excede o limite de {MAX_FINDINGS} findings.")
    base = {"source_tool": meta.get("source_tool", "import"),
            "environment": meta.get("environment", "unknown")}
    if meta.get("asset_name"):
        base["asset_name"] = meta["asset_name"]
    out = []
    for it in items:
        if isinstance(it, dict):
            out.append(coerce_finding(it, base))
    return out


def parse_grype(content: dict[str, Any], meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Parser do Grype (`grype -o json`) — vulnerabilidades de pacotes/imagem."""
    if not isinstance(content, dict):
        raise ValueError("JSON do Grype inválido (esperado objeto).")
    src = content.get("source") or {}
    tgt = src.get("target") or {}
    asset = tgt.get("userInput") if isinstance(tgt, dict) else (tgt if isinstance(tgt, str) else None)
    asset = asset or meta.get("asset_name") or "unknown"
    asset_type = "image" if str(src.get("type", "")).lower() in ("image", "docker") else "filesystem"
    base = {"source_tool": "grype", "asset_name": asset, "asset_type": asset_type,
            "environment": meta.get("environment", "unknown")}
    out = []
    for m in (content.get("matches") or []):
        if not isinstance(m, dict):
            continue
        vuln = m.get("vulnerability") or {}
        art = m.get("artifact") or {}
        fix = vuln.get("fix") or {}
        fixed = (fix.get("versions") or [None])[0]
        cvss = None
        for c in (vuln.get("cvss") or []):
            mv = (c.get("metrics") or {}).get("baseScore")
            if mv is not None:
                try:
                    cvss = max(cvss or 0, float(mv))
                except (TypeError, ValueError):
                    pass
        loc = (art.get("locations") or [{}])
        out.append(coerce_finding({
            "source_type": "dependency", "category": "vulnerability", "subcategory": art.get("type"),
            "title": vuln.get("id") or "Vulnerabilidade",
            "description": vuln.get("description"),
            "severity": vuln.get("severity"), "cve": vuln.get("id"), "cvss": cvss,
            "package_name": art.get("name"), "installed_version": art.get("version"),
            "fixed_version": fixed, "references": vuln.get("urls") or [],
            "file_path": loc[0].get("path") if loc and isinstance(loc[0], dict) else None,
            "remediation": (f"Atualizar {art.get('name')} para {fixed}" if fixed else None),
        }, base))
        if len(out) > MAX_FINDINGS:
            raise ValueError(f"Lote excede o limite de {MAX_FINDINGS} findings.")
    return out


def parse_gitleaks(content: Any, meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Parser do Gitleaks (`gitleaks -f json`) — segredos. Sempre mascarado."""
    if not isinstance(content, list):
        raise ValueError("JSON do Gitleaks inválido (esperado lista).")
    if len(content) > MAX_FINDINGS:
        raise ValueError(f"Lote excede o limite de {MAX_FINDINGS} findings.")
    base = {"source_tool": "gitleaks", "asset_type": "repo",
            "asset_name": meta.get("asset_name") or "repository",
            "environment": meta.get("environment", "unknown")}
    out = []
    for s in content:
        if not isinstance(s, dict):
            continue
        out.append(coerce_finding({
            "source_type": "secret", "category": "secret", "confidence": "high", "severity": "high",
            "subcategory": s.get("RuleID"),
            "title": f"Segredo: {s.get('Description') or s.get('RuleID') or 'exposto'}",
            "file_path": s.get("File"),
            "evidence": {
                "rule": s.get("RuleID"), "start_line": s.get("StartLine"),
                "commit": s.get("Commit"), "author": s.get("Author"),
                "match_masked": mask_secret(s.get("Secret") or s.get("Match")),
            },
            "remediation": "Remover o segredo do repositório/histórico e rotacioná-lo.",
        }, base))
    return out


def parse_npm_audit(content: dict[str, Any], meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Parser do `npm audit --json` (npm >= 7)."""
    if not isinstance(content, dict):
        raise ValueError("JSON do npm audit inválido.")
    vulns = content.get("vulnerabilities") or {}
    base = {"source_tool": "npm-audit", "asset_type": "dependency",
            "asset_name": meta.get("asset_name") or "node-project",
            "environment": meta.get("environment", "unknown")}
    out = []
    for name, v in vulns.items():
        if not isinstance(v, dict):
            continue
        via = next((x for x in (v.get("via") or []) if isinstance(x, dict)), {})
        fix = v.get("fixAvailable")
        fixed = fix.get("version") if isinstance(fix, dict) else None
        out.append(coerce_finding({
            "source_type": "dependency", "category": "vulnerability", "subcategory": "npm",
            "title": via.get("title") or f"Vulnerabilidade em {name}",
            "severity": v.get("severity"),
            "package_name": name, "installed_version": v.get("range"), "fixed_version": fixed,
            "cve": (via.get("cwe") or [None])[0] if str(via.get("cwe", "")).startswith("CVE") else None,
            "cwe": (via.get("cwe") or [None])[0], "cvss": (via.get("cvss") or {}).get("score"),
            "references": [via.get("url")] if via.get("url") else [],
        }, base))
    return out


def parse_pip_audit(content: Any, meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Parser do `pip-audit -f json` (formatos {dependencies:[...]} ou lista)."""
    deps = content.get("dependencies") if isinstance(content, dict) else content
    if not isinstance(deps, list):
        raise ValueError("JSON do pip-audit inválido.")
    base = {"source_tool": "pip-audit", "asset_type": "dependency",
            "asset_name": meta.get("asset_name") or "python-project",
            "environment": meta.get("environment", "unknown")}
    out = []
    for dep in deps:
        if not isinstance(dep, dict):
            continue
        for v in (dep.get("vulns") or dep.get("vulnerabilities") or []):
            aliases = v.get("aliases") or []
            cve = next((a for a in aliases if str(a).upper().startswith("CVE")), None)
            out.append(coerce_finding({
                "source_type": "dependency", "category": "vulnerability", "subcategory": "pip",
                "title": v.get("id") or f"Vulnerabilidade em {dep.get('name')}",
                "description": v.get("description"), "severity": v.get("severity") or "medium",
                "package_name": dep.get("name"), "installed_version": dep.get("version"),
                "fixed_version": (v.get("fix_versions") or [None])[0],
                "cve": cve or v.get("id"),
            }, base))
            if len(out) > MAX_FINDINGS:
                raise ValueError(f"Lote excede o limite de {MAX_FINDINGS} findings.")
    return out


def parse_lynis(content: Any, meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Parser do Lynis (texto de `lynis-report.dat`) — hardening de host Linux."""
    if not isinstance(content, str):
        raise ValueError("Lynis espera o conteúdo texto do lynis-report.dat.")
    hostname = meta.get("asset_name")
    idx = None
    warnings: list[str] = []
    suggestions: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("hostname=") and not hostname:
            hostname = line.split("=", 1)[1]
        elif line.startswith("hardening_index="):
            idx = line.split("=", 1)[1]
        elif line.startswith("warning[]="):
            warnings.append(line.split("=", 1)[1])
        elif line.startswith("suggestion[]="):
            suggestions.append(line.split("=", 1)[1])
    hostname = hostname or "linux-host"
    base = {"source_tool": "lynis", "asset_type": "host", "asset_name": hostname,
            "host_name": hostname, "environment": meta.get("environment", "unknown"),
            "category": "hardening", "source_type": "host"}
    out = []
    for w in warnings[:MAX_FINDINGS]:
        parts = w.split("|")
        out.append(coerce_finding({
            "severity": "high", "subcategory": parts[0] if parts else None,
            "title": parts[1] if len(parts) > 1 and parts[1] else (parts[0] or "Aviso de hardening"),
            "remediation": parts[3] if len(parts) > 3 and parts[3] not in ("-", "") else None,
            "tags": [f"hardening_index:{idx}"] if idx else [],
        }, base))
    for s in suggestions[:MAX_FINDINGS]:
        parts = s.split("|")
        out.append(coerce_finding({
            "severity": "low", "confidence": "medium", "subcategory": parts[0] if parts else None,
            "title": parts[1] if len(parts) > 1 and parts[1] else (parts[0] or "Sugestão de hardening"),
            "remediation": parts[3] if len(parts) > 3 and parts[3] not in ("-", "") else None,
        }, base))
    return out


ADAPTERS = {
    "trivy": parse_trivy,
    "grype": parse_grype,
    "gitleaks": parse_gitleaks,
    "npm_audit": parse_npm_audit,
    "pip_audit": parse_pip_audit,
    "lynis": parse_lynis,
    "normalized": parse_normalized,
}


def run_adapter(fmt: str, content: Any, meta: dict[str, Any]) -> list[dict[str, Any]]:
    fn = ADAPTERS.get(fmt)
    if not fn:
        raise ValueError(f"Formato de ingestão não suportado: {fmt}")
    return fn(content, meta)
