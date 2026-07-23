# Amostras de scanners (para testar a ingestão de findings)

Arquivos de **exemplo** para exercitar a Central de Findings (Security Ops →
Achados → *Ingerir resultado de scanner*). São dados fictícios de demonstração —
não representam a infraestrutura real.

| Arquivo | Ferramenta | O que demonstra |
|---|---|---|
| `trivy/image-web-app.json` | Trivy | Imagem: vuln OS (curl/zlib) + misconfig Dockerfile + segredo Stripe (mascarado) |
| `trivy/fs-python-service.json` | Trivy | Filesystem: deps Python (jinja2/requests) + senha hardcoded |
| `trivy/fs-node-frontend.json` | Trivy | Filesystem: deps Node (braces/semver) |
| `trivy/image-legacy-db.json` | Trivy | Imagem legada (CentOS 7): sudo Baron Samedit, glibc — várias críticas |
| `grype/image-api.json` | Grype | Vulnerabilidades (nginx HTTP/2 Rapid Reset, OpenSSH regreSSHion) |
| `gitleaks/repo-secrets.json` | Gitleaks | Segredos em repositório (AWS key, chave RSA) — **sempre mascarados** |
| `lynis/lynis-report.dat` | Lynis | Hardening Linux (root SSH, umask, firewall ausente, core dumps…) |

## Como ingerir

**Pela UI:** Security Ops → Achados → escolha a ferramenta no seletor, informe o
ambiente e selecione o arquivo correspondente.

**Pela API:**
```bash
curl -sS -X POST https://ad-audit.astra-sa.com/api/v1/security/findings/ingest \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"format":"trivy","environment":"production","content":'"$(cat samples/trivy/image-web-app.json)"'}'
```

## Como gerar de verdade

```bash
trivy image   -f json -o out.json  registry.local/minha-imagem:tag
trivy fs      -f json -o out.json  .
grype         registry.local/minha-imagem:tag -o json > out.json
gitleaks detect -f json -r out.json
npm audit --json > out.json
pip-audit -f json -o out.json
lynis audit system      # depois envie /var/log/lynis-report.dat
```

> Segurança: a ingestão **valida e limita** o payload, **mascara segredos** e
> **não executa comandos** (não é caminho de RCE). Requer RBAC
> (`investigation:manage`) e é auditada.
