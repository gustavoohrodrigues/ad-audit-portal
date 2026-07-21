# AD Audit Portal

Central **somente leitura** de auditoria, investigação e observabilidade de
identidades do **Microsoft Active Directory**. Responde rapidamente a perguntas
como *"o usuário está bloqueado?"*, *"qual máquina originou o bloqueio?"*,
*"quem redefiniu a senha?"*, *"houve alteração em grupo privilegiado?"* — com
dashboard operacional no estilo **Dark Ops / NOC**, painel de investigação de
bloqueios, pontuação de risco e alertas.

> ⚠️ **A aplicação nunca altera o Active Directory.** Não há desbloqueio, reset
> de senha, criação/exclusão/habilitação de contas nem gestão de grupos. Toda a
> integração com o AD é feita por conta de serviço com **privilégio mínimo de
> leitura** via **LDAPS**. Isso é garantido inclusive por teste automatizado
> (`tests/backend/test_api_security.py::test_no_ad_write_endpoints`).

---

## Sumário

- [Arquitetura](#arquitetura)
- [Início rápido](#início-rápido)
- [Serviços](#serviços)
- [RBAC](#rbac-controle-de-acesso)
- [Eventos coletados](#eventos-coletados)
- [Segurança](#segurança)
- [Documentação](#documentação)
- [Testes](#testes)

---

## Arquitetura

```
                        ┌──────────────────────────┐
   NGINX Proxy Manager  │  (TLS / roteamento externo — SUA infraestrutura)
   (externo, seu)       └───────────┬──────────────┘
                                    │ HTTP
                          ┌─────────▼──────────┐
                          │  frontend (SPA +   │  React + TS (Vite), nginx
                          │  proxy /api)       │  não-root :8080
                          └─────────┬──────────┘
                                    │ /api → backend
      ┌───────────────┬────────────┼─────────────┬───────────────┐
      │               │            │             │               │
┌─────▼─────┐   ┌─────▼─────┐ ┌────▼─────┐  ┌─────▼─────┐   ┌──────▼──────┐
│  backend  │   │ collector │ │  worker  │  │   beat    │   │  (migrate)  │
│ FastAPI   │   │ WEF/SIEM  │ │  Celery  │  │  Celery   │   │  Alembic    │
└─────┬─────┘   └─────┬─────┘ └────┬─────┘  └─────┬─────┘   └──────┬──────┘
      │               │            │              │                │
      └───────┬───────┴────────────┴──────┬───────┴────────────────┘
              │                            │
        ┌─────▼─────┐               ┌──────▼──────┐
        │ postgres  │               │    redis    │
        │  :5432    │               │   :6379     │
        └───────────┘               └─────────────┘

   Active Directory  ◄── LDAPS (leitura) ── backend
   Domain Controllers ── WEF/WinRM/SIEM ──► collector
```

Ver [`docs/architecture.md`](docs/architecture.md) para os diagramas detalhados
(arquitetura e fluxo de eventos em Mermaid).

---

## Início rápido

Pré-requisitos: **Docker** + **Docker Compose v2**.

```bash
# 1. Gera .env com segredos aleatórios e placeholders necessários
./scripts/setup.sh

# 2. Ajuste o .env — principalmente a seção ACTIVE DIRECTORY / LDAP
#    (URI dos DCs, conta de serviço, bases de busca) e os grupos de RBAC.
$EDITOR .env

# 3. Coloque o certificado da CA do AD (para validar o LDAPS)
#    em secrets/ad_ca_certificate.pem  (ver secrets/README.md)

# 4. Build + subir a stack (migrations rodam automaticamente)
docker compose build
docker compose up -d

# 5. (Opcional) dados de demonstração para conhecer a interface
./scripts/seed_demo.sh

# 6. Verificar saúde
./scripts/healthcheck.sh
```

Aponte o **NGINX Proxy Manager** para o serviço `frontend`
(porta publicada `FRONTEND_PUBLISH_PORT`, padrão `8088`). Ver
[`docs/npm.md`](docs/npm.md).

- API + Swagger: `https://<seu-host>/api/docs`
- Métricas Prometheus: `https://<seu-host>/api/v1/metrics`
- Health / readiness: `/api/v1/health` · `/api/v1/readiness`

Para produção use também o override:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## Serviços

| Serviço | Stack | Função |
|---|---|---|
| `frontend` | React + TS + Vite, nginx (não-root) | SPA Dark Ops/NOC; serve o app e faz proxy `/api` → backend |
| `backend` | Python + FastAPI + SQLModel | API REST (OpenAPI), auth LDAP+JWT, RBAC, LDAPS leitura, métricas |
| `collector` | Python (async) | Coleta/normalização de eventos (WEF primário; WinRM/Elastic/Wazuh/Graylog/Splunk) |
| `worker` | Celery | Correlação, risco, alertas, webhook, GLPI, retenção |
| `beat` | Celery beat | Agendamento das tarefas periódicas |
| `postgres` | PostgreSQL 16 | Armazenamento; índices para busca rápida |
| `redis` | Redis 7 | Cache, fila Celery, rate limit, revogação de refresh token |
| `migrate` | Alembic | Aplica migrations e encerra (dependência dos demais) |

> O **reverse-proxy interno foi omitido** conforme sua infraestrutura já possui
> o **NGINX Proxy Manager (NPM)**. Os headers de segurança recomendados para
> configurar no NPM estão em [`docs/npm.md`](docs/npm.md).

---

## RBAC (controle de acesso)

Perfis mapeados a grupos do AD (definidos no `.env`):

| Perfil | Grupo AD (`.env`) | Capacidades |
|---|---|---|
| `viewer` | `AUTH_GROUP_VIEWERS` | Dashboard e dados básicos. Sem JSON bruto, sem export. |
| `helpdesk` | `AUTH_GROUP_HELPDESK` | Consulta de usuário, bloqueios, eventos de senha; observação e ticket. |
| `security_analyst` | `AUTH_GROUP_SECURITY` | JSON bruto, correlação avançada, export, contas críticas, investigações. |
| `administrator` | `AUTH_GROUP_ADMINS` | Configuração de fontes, alertas, integrações, RBAC, retenção. |

A role é resolvida a partir do `memberOf` do usuário no login; o maior
privilégio vence. Acessos sensíveis (login, JSON bruto, exportações) são
**auditados** em `internal_audit_log`.

---

## Eventos coletados

Bloqueio (`4740`, tratamento especial), logon/falha (`4624`/`4625`/`4771`/`4776`),
senha (`4723` troca própria / `4724` reset por operador), conta
(`4720`/`4722`/`4725`/`4726`/`4738`/`4767`/`4781`), grupos
(`4728`/`4732`/`4756` add, `4729`/`4733`/`4757` remove) e Directory Service
(`5136`/`5137`/`5141`).

**Deduplicação:** índice único `(domain_controller, event_record_id, event_id)`
+ `ON CONFLICT DO NOTHING`. **Checkpoint por fonte** evita reprocessamento.

Ver [`docs/wef.md`](docs/wef.md) e [`docs/gpo-audit.md`](docs/gpo-audit.md).

---

## Segurança

- LDAPS obrigatório com validação de certificado da CA.
- Proteção contra LDAP Injection (escape de filtros), SQL Injection (queries
  parametrizadas/ORM), XSS/CSRF (cookies httpOnly+SameSite, CSP), SSRF
  (integrações restritas por configuração).
- JWT com expiração curta + refresh token rotacionado e revogável (Redis).
- Rate limiting (global e específico para login).
- Segredos nunca vão para logs (redação automática de senhas/tokens/URLs).
- Containers **não-root**, imagens **multi-stage** mínimas.
- Retenção/expurgo automático e mascaramento de dados (LGPD).

Detalhes em [`docs/hardening.md`](docs/hardening.md).

---

## Documentação

| Guia | Conteúdo |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Diagramas de arquitetura e fluxo de eventos |
| [`docs/installation.md`](docs/installation.md) | Instalação passo a passo |
| [`docs/upgrade.md`](docs/upgrade.md) | Atualização de versão |
| [`docs/ldap.md`](docs/ldap.md) | LDAP/LDAPS, conta de serviço e **permissões mínimas** |
| [`docs/wef.md`](docs/wef.md) | Windows Event Forwarding, subscription e GPO |
| [`docs/gpo-audit.md`](docs/gpo-audit.md) | Política de auditoria avançada |
| [`docs/glpi.md`](docs/glpi.md) | Integração GLPI |
| [`docs/zabbix-prometheus.md`](docs/zabbix-prometheus.md) | Observabilidade |
| [`docs/hardening.md`](docs/hardening.md) | Endurecimento de segurança |
| [`docs/backup-restore.md`](docs/backup-restore.md) | Backup e restauração |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Solução de problemas |
| [`docs/npm.md`](docs/npm.md) | Configuração do NGINX Proxy Manager |

---

## Testes

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt -r tests/requirements.txt
pytest            # unitários, integração e segurança
```

Cobrem: conversão de atributos AD (FILETIME/SID/GUID/UAC), motor de risco, RBAC,
normalização de eventos, proteção contra LDAP Injection, redação de logs e
verificação de que **nenhum endpoint altera o AD**.

---

## Licença

Uso interno. Ajuste conforme a política da sua organização.
