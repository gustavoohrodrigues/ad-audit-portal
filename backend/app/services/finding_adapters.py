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


ADAPTERS = {"trivy": parse_trivy, "normalized": parse_normalized}


def run_adapter(fmt: str, content: Any, meta: dict[str, Any]) -> list[dict[str, Any]]:
    fn = ADAPTERS.get(fmt)
    if not fn:
        raise ValueError(f"Formato de ingestão não suportado: {fmt}")
    return fn(content, meta)
