# Guia de Endurecimento (Hardening)

Recomendações de segurança para operar o AD Audit Portal em produção. O portal é **somente leitura** do Active Directory; ainda assim, ele concentra dados sensíveis de segurança (eventos, contas privilegiadas, bloqueios), exigindo controles rigorosos.

---

## 1. TLS no proxy (NPM externo)

O TLS é terminado em um **proxy reverso externo** (Nginx Proxy Manager — NPM). Diretrizes:

- Emitir/renovar certificado válido (Let's Encrypt ou CA corporativa) para o FQDN do portal.
- Forçar **HTTPS** e redirecionar HTTP → HTTPS.
- Habilitar apenas **TLS 1.2/1.3**; desabilitar TLS ≤ 1.1 e cifras fracas.
- Habilitar **HSTS** no NPM (o app não define HSTS por padrão, pois o TLS termina no proxy):

```nginx
# Advanced / Custom Nginx Config no NPM (host do portal)
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
```

- Apenas o **frontend** deve ser publicado pelo proxy; backend, worker, collector e banco permanecem na rede interna (ver seção 6).

---

## 2. Cabeçalhos de segurança

A aplicação já envia:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY` (anti-clickjacking)
- `Referrer-Policy` (restritiva)
- `Content-Security-Policy` (CSP)

Recomendações complementares:

- **HSTS** deve ser adicionado no **NPM** (seção 1), não na app.
- Revise a **CSP** ao adicionar integrações de front-end; mantenha `default-src 'self'` e evite `unsafe-inline`/`unsafe-eval`.
- Verifique os headers em produção:

```bash
curl -sSI https://portal.empresa.local/ | grep -iE \
  'strict-transport|x-content-type|x-frame|referrer-policy|content-security'
```

---

## 3. LDAPS com validação de certificado

- `AD_LDAP_TLS_VERIFY=true` (obrigatório em produção).
- CA em **Docker Secret**: `AD_LDAP_CA_CERT_PATH=/run/secrets/ad_ca_certificate.pem` (arquivo `secrets/ad_ca_certificate.pem`).
- Usar `ldaps://...:636` (não LDAP simples na 389).
- Conta de serviço com **menor privilégio** e **somente leitura** — detalhes em **`ldap.md`** (seção "Permissões mínimas").

---

## 4. Rotação de segredos

Gere segredos fortes e rotacione-os periodicamente:

```bash
# Chaves de aplicação/JWT
openssl rand -hex 48   # APP_SECRET_KEY
openssl rand -hex 48   # JWT_SECRET_KEY
```

- Rotacione `APP_SECRET_KEY`, `JWT_SECRET_KEY`, `AD_BIND_PASSWORD`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN` e senhas de banco em cronograma definido (ex.: trimestral) e após qualquer suspeita de vazamento.
- A rotação do `JWT_SECRET_KEY` invalida sessões emitidas (relogin) — planeje janela.
- Nunca versione segredos; mantenha-os fora do Git (ver `.gitignore`).

---

## 5. Docker Secrets / Vault

- Preferir **Docker Secrets** (montados em `/run/secrets/...`) ou **HashiCorp Vault** para todos os segredos (senha LDAP, tokens GLPI, chaves da app, credenciais de banco).
- Evitar segredos em texto claro no `.env` de produção; quando inevitável, restrinja permissões do arquivo (`chmod 600`) e o acesso ao host.
- Rotacione o certificado da CA (`secrets/ad_ca_certificate.pem`) quando a PKI interna renovar.

---

## 6. Containers não-root e rede isolada

- Os serviços já rodam como usuários **não-root** dedicados (UIDs **10001/10002/10003**) e o front usa **`nginx-unprivileged`**.
- Mantenha `read_only: true` no filesystem dos containers onde possível, com `tmpfs` para diretórios de escrita temporária.
- Adote `cap_drop: [ALL]` e `security_opt: [no-new-privileges:true]`.
- **Rede interna isolada:** apenas o **frontend** publica porta ao host/proxy; backend, worker, collector, banco e cache ficam em rede Docker interna sem publicação de portas.
- O volume `wefspool` (`/data/wef-spool`) deve ser acessível apenas ao collector e ao produtor de NDJSON.

Exemplo (trecho de `docker-compose`):

```yaml
services:
  backend:
    user: "10001:10001"
    read_only: true
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    tmpfs: ["/tmp"]
    networks: [internal]         # sem "ports:" — não publicado
  frontend:
    user: "10003:10003"
    ports: ["127.0.0.1:8080:8080"]  # apenas o front é publicado (para o NPM)
    networks: [internal, edge]
networks:
  internal:
    internal: true
  edge: {}
```

---

## 7. Rate limiting

Habilite/ajuste o rate limiting da aplicação (variáveis `RATE_LIMIT_*`), especialmente no endpoint de login, para mitigar brute force:

```dotenv
RATE_LIMIT_ENABLED=true
RATE_LIMIT_LOGIN_PER_MINUTE=5
RATE_LIMIT_API_PER_MINUTE=120
RATE_LIMIT_BURST=20
```

- Reforce com rate limiting no NPM (`limit_req`) como segunda camada.
- Monitore `adaudit_login_attempts_total{result="failed"}` (ver `zabbix-prometheus.md`) para detectar ataques.

---

## 8. Menor privilégio da conta de serviço

A conta de bind LDAP deve ter **apenas leitura**, sem escrita, sem reset de senha e fora de grupos privilegiados. Consulte **`ldap.md` → seção "Permissões mínimas (menor privilégio)"** para o passo a passo com `Delegation of Control Wizard` e `dsacls`.

Da mesma forma, a conta de leitura de eventos (`svc_ad_event_reader`, usada no conector WinRM) deve pertencer apenas ao grupo **Event Log Readers** (ver `wef.md`).

---

## 9. Retenção, expurgo e manutenção de banco

Defina políticas de retenção alinhadas à necessidade operacional e à LGPD:

```dotenv
EVENT_RETENTION_DAYS=365          # eventos normalizados/correlacionados
EVENT_RAW_RETENTION_DAYS=90       # payload bruto (mais sensível, retenção menor)
AUDIT_LOG_RETENTION_DAYS=730      # trilha de auditoria do próprio portal
NOTIFICATION_RETENTION_DAYS=180   # histórico de entregas de notificações
INACTIVE_ACCOUNT_DAYS=90          # janela de inatividade para relatórios
```

- Mantenha a retenção do **evento bruto** menor que a do evento normalizado (reduz superfície de dados sensíveis).
- O expurgo é **automático e auditável**: o worker/beat executa a política diariamente (hora definida em `MAINTENANCE_CRON_HOUR`), removendo eventos, JSON bruto, auditoria e histórico de notificações fora da janela e registrando em `retention_policies`.

### Limpeza e recuperação de espaço (anti-sobrecarga)

Além da retenção, o portal oferece manutenção ativa do PostgreSQL para evitar crescimento descontrolado e bloat:

- **Purga em lotes** (`ctid`, sem lock longo) para não travar o banco em tabelas grandes.
- **VACUUM ANALYZE** ao final (`MAINTENANCE_VACUUM_ENABLED=true`) recupera espaço de linhas mortas e atualiza estatísticas do planner.
- **`statement_timeout` por sessão** (`DB_STATEMENT_TIMEOUT_MS=30000`) impede que uma query travada consuma o banco.

Formas de disparar:

```bash
# 1) UI (admin): página "Capacidade & Performance" → seção "Manutenção do Banco":
#    - campo "Limpar JSON bruto de eventos com mais de N dias" (libera volume)
#    - "Executar limpeza"           → purga + VACUUM ANALYZE
#    - "Recuperar espaço (VACUUM FULL)" → encolhe o arquivo em disco de fato
# 2) API (admin): POST /api/v1/admin/maintenance/cleanup?full=true&raw_days=7
#    (audita db_cleanup / db_cleanup_full)
#    Status:       GET  /api/v1/admin/maintenance/status
# 3) Host cron (VACUUM ANALYZE nas tabelas de maior rotatividade):
./scripts/db-maintenance.sh
```

> **Reduzir o tamanho de fato:** o maior consumo é o `raw_event_json` do
> `normalized_events`. Um `VACUUM` comum apenas marca o espaço como reutilizável
> — **não** encolhe o arquivo. Para devolver espaço ao SO:
> 1. Reduza o horizonte do JSON bruto (`raw_days` na UI, ou `EVENT_RAW_RETENTION_DAYS`
>    no `.env`) para esvaziar o JSON de eventos além desse período; e
> 2. rode **VACUUM FULL** (botão "Recuperar espaço" ou `?full=true`), que reescreve
>    a tabela e libera o disco (lock exclusivo breve).

Exemplo de cron no host (03h, complementando a retenção automática do worker):

```cron
0 3 * * *  cd /mnt/gv0/ad-audit && ./scripts/db-maintenance.sh >> /var/log/ad-audit-maint.log 2>&1
```

A limpeza via API/UI é **protegida por RBAC (administrator)**, usa **lock no Redis** (`maintenance:cleanup:lock`) para evitar execução concorrente e é **auditada**.

---

## 10. LGPD e dados sensíveis

- `MASK_SENSITIVE_DATA=true` — mascara dados pessoais na interface/relatórios para papéis sem necessidade de ver o dado cru.
- `AUDIT_RAW_EVENT_ACCESS_SECURITY_ONLY=true` — restringe o acesso a **eventos brutos** apenas ao papel de Segurança e **registra cada acesso** (métrica `adaudit_raw_event_access_total`).
- Aplique o RBAC (`AUTH_GROUP_VIEWERS/HELPDESK/SECURITY/ADMINS`) segundo o princípio da necessidade de conhecer.
- Documente base legal, finalidade e prazo de retenção do tratamento de dados de logon/contas.

---

## 11. Scan de vulnerabilidades no CI e dependências

- Adicione **scan de imagens** ao pipeline (Trivy ou Grype), falhando o build em vulnerabilidades HIGH/CRITICAL:

```yaml
# Exemplo GitHub Actions
- name: Trivy image scan
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: 'registry.empresa.local/ad-audit-portal/backend:${{ github.sha }}'
    severity: 'HIGH,CRITICAL'
    exit-code: '1'
    ignore-unfixed: true
```

```bash
# Alternativa local com Grype
grype registry.empresa.local/ad-audit-portal/backend:latest --fail-on high
```

- Habilite **Dependabot** ou **Renovate** para atualizações de dependências (Python, Node, imagens base):

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule: { interval: "weekly" }
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule: { interval: "weekly" }
  - package-ecosystem: "docker"
    directory: "/"
    schedule: { interval: "weekly" }
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "weekly" }
```

---

## 12. Override de hardening de containers e verificação automática

O repositório inclui um override pronto que aplica os controles de runtime da seção 6 sem editar os compose principais:

```bash
# Subir com hardening aplicado (junto dos demais overrides):
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.ceph.yml \
  -f docker-compose.hardening.yml up -d
```

`docker-compose.hardening.yml` aplica a todos os serviços de aplicação: `security_opt: no-new-privileges:true`, `cap_drop: ALL`, `pids_limit` (anti fork-bomb) e limite de descritores de arquivo (`ulimits.nofile`). Postgres e Redis recebem um perfil mais conservador para não quebrar o `chown`/entrypoint oficial.

Após subir, valide o estado com o script de verificação (não altera nada, imprime PASS/WARN):

```bash
./scripts/hardening-check.sh
```

Ele confere: containers rodando como não-root, `no-new-privileges`, cabeçalhos de segurança, `statement_timeout` ativo, permissão do `.env`, `APP_DEBUG=false`, LDAPS e exposição de portas.

---

## 13. Checklist final de hardening

- [ ] NPM com TLS 1.2/1.3, redirect HTTP→HTTPS e **HSTS** habilitado.
- [ ] Headers de segurança presentes (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP).
- [ ] `AD_LDAP_TLS_VERIFY=true` e CA via Docker Secret.
- [ ] Conta de bind LDAP **somente leitura**, fora de grupos privilegiados (ver `ldap.md`).
- [ ] Segredos em Docker Secrets/Vault; `APP_SECRET_KEY`/`JWT_SECRET_KEY` gerados com `openssl rand -hex 48`.
- [ ] Rotação de segredos agendada e documentada.
- [ ] Containers não-root (10001/10002/10003, nginx-unprivileged), `no-new-privileges`, `cap_drop ALL`, FS read-only onde possível.
- [ ] Rede interna isolada; apenas o frontend publicado.
- [ ] Rate limiting ativo no app e no NPM.
- [ ] Retenção/expurgo configurados (`EVENT_RETENTION_DAYS`, `EVENT_RAW_RETENTION_DAYS`, `AUDIT_LOG_RETENTION_DAYS`, `NOTIFICATION_RETENTION_DAYS`).
- [ ] Manutenção de banco ativa: `MAINTENANCE_VACUUM_ENABLED=true`, `DB_STATEMENT_TIMEOUT_MS` definido, `docker-compose.hardening.yml` aplicado e `./scripts/hardening-check.sh` sem WARN crítico.
- [ ] LGPD: `MASK_SENSITIVE_DATA=true`, `AUDIT_RAW_EVENT_ACCESS_SECURITY_ONLY=true`.
- [ ] `/api/v1/metrics` restrito à rede de monitoramento.
- [ ] Scan Trivy/Grype no CI e Dependabot/Renovate ativos.
- [ ] Backups do banco criptografados e testados (restore).
- [ ] Trilha de auditoria do portal monitorada (acessos a eventos brutos, ações administrativas).
