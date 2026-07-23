# Security Operations — Camada de Findings

Módulo de operações de segurança que **agrega, normaliza, prioriza e rastreia**
achados de múltiplos scanners (Trivy, e adapters futuros: Lynis, coletor Linux,
parsers de contêiner, Grype/Syft/Gitleaks/Checkov via import normalizado).

> Somente leitura no AD. Nenhuma ação deste módulo escreve no Active Directory.

## Arquitetura

```
scanner (Trivy/Lynis/…) → JSON → [ingestão validada] → adapter → modelo canônico
   → dedup por fingerprint → security_findings → risco → UI/alertas/relatórios
```

- **Modelo único** (`security_findings`) para qualquer fonte — filtros e
  correlação atravessam ferramentas.
- **Deduplicação por fingerprint estável** (re-scan atualiza o mesmo registro,
  incrementa `occurrences`, preserva supressão vigente).
- **Risco prático** (0–100) combinando severidade + contexto (exploit,
  exposição à internet, contexto privilegiado, ambiente de produção, existência
  de correção, confiança).
- **Linhagem** (`finding_ingestions`): cada import é rastreável (quem, quando,
  fonte, totais).

## Segurança da ingestão (secure coding)

- Validação estrita (Pydantic) + `coerce_finding` (limita tamanhos, restringe
  enums, sanitiza).
- **Segredos nunca são armazenados crus** — mascarados no adapter e re-mascarados
  na coerção (defesa em profundidade).
- **Sem subprocess/eval** — só parsing de dados fornecidos → a ingestão não é
  caminho de RCE.
- Limite de corpo (`FINDINGS_INGEST_MAX_BYTES`) e de nº de findings por lote.
- RBAC: leitura `critical:read`; ingestão/supressão `investigation:manage`.
- Toda escrita é **auditada** (`findings_ingest`, `finding_suppress`,
  `finding_state`).
- Busca com `ILIKE` escapado (sem SQL cru); paginação limitada.

## Como ingerir (Trivy)

```bash
# Vulnerabilidades + segredos + misconfig de uma imagem
trivy image -f json -o app.json minha-imagem:tag

# Filesystem (deps Python/Node, segredos, misconfig)
trivy fs -f json -o repo.json .
```

Na UI: **Security Ops → Todos os Achados → Ingerir resultado de scan (Trivy JSON)**,
selecione o ambiente e o arquivo. Também há a rota `POST /api/v1/security/findings/ingest`
com `{ "format": "trivy", "environment": "production", "content": <json> }`.

Import normalizado genérico (para Lynis/coletor/osquery já mapeados):
`{ "format": "normalized", "content": [ {finding...}, ... ] }`.

## Fluxo de triagem

- **Corrigir primeiro**: fila ordenada por risco na Visão Geral.
- **Supressão** com motivo obrigatório e expiração (auditada; reabre no
  vencimento ou em novo scan).
- **Estado de remediação**: `none | in_progress | fixed | wont_fix`
  (`fixed` marca o achado como resolvido).

## Roadmap de adapters (incremental, mesmo modelo)

- Lynis (hardening Linux) → `category=hardening`, `asset_type=host`.
- Coletor Linux estruturado (SSH/sudoers/portas/kernel) via import normalizado.
- Parsers de contêiner/compose/swarm (privilégios, socket exposto, root FS).
- Grype/Syft(SBOM)/Gitleaks/Checkov/osquery via import normalizado ou adapter.

Cada novo adapter apenas retorna findings no modelo canônico — nenhuma mudança
de UI/DB é necessária.
