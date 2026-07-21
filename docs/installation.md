# Guia de Instalação

## Pré-requisitos

- Docker Engine 24+ e Docker Compose v2.
- Acesso de rede aos Domain Controllers via **LDAPS (636/tcp)**.
- Certificado da CA que assina o LDAPS dos DCs.
- Um servidor Windows Event Collector (WEF) ou um SIEM já coletando o log
  Security dos DCs (ver [`wef.md`](wef.md)).
- NGINX Proxy Manager (ou outro proxy) para TLS e roteamento externo.

## 1. Obter o código e preparar o ambiente

```bash
git clone <seu-repositorio> ad-audit-portal
cd ad-audit-portal
./scripts/setup.sh
```

O `setup.sh` cria o `.env` a partir do `.env.example` gerando automaticamente
`APP_SECRET_KEY`, `JWT_SECRET_KEY`, `POSTGRES_PASSWORD` e `REDIS_PASSWORD`
fortes, e ajusta `DATABASE_URL`/`REDIS_URL` de acordo. **O `.env` nunca deve ser
versionado.**

## 2. Configurar o Active Directory

Edite o `.env` e ajuste ao menos:

```ini
AD_DOMAIN=empresa.local
AD_BASE_DN=DC=empresa,DC=local
AD_LDAP_URI=ldaps://dc01.empresa.local:636
AD_LDAP_FALLBACK_URI=ldaps://dc02.empresa.local:636
AD_BIND_USERNAME=svc_ad_audit@empresa.local
AD_BIND_PASSWORD=<senha-da-conta-de-servico>
AD_BIND_DN=CN=svc_ad_audit,OU=Service Accounts,DC=empresa,DC=local
AD_USERS_SEARCH_BASE=OU=Usuarios,DC=empresa,DC=local
AD_GROUPS_SEARCH_BASE=OU=Grupos,DC=empresa,DC=local

AUTH_GROUP_VIEWERS=GG_AD_AUDIT_VIEWERS
AUTH_GROUP_HELPDESK=GG_AD_AUDIT_HELPDESK
AUTH_GROUP_SECURITY=GG_AD_AUDIT_SECURITY
AUTH_GROUP_ADMINS=GG_AD_AUDIT_ADMINS
```

Ver [`ldap.md`](ldap.md) para criar a conta de serviço com **permissões
mínimas** e [`gpo-audit.md`](gpo-audit.md) para a política de auditoria.

## 3. Certificado da CA (LDAPS)

Coloque o certificado da CA (PEM) em `secrets/ad_ca_certificate.pem`. Ver
[`secrets/README.md`](../secrets/README.md) para exportá-lo. Mantenha
`AD_LDAP_TLS_VERIFY=true`.

## 4. Coleta de eventos

Escolha o modo em `EVENT_COLLECTOR_MODE` (`wef` recomendado). Para WEF, garanta
que os eventos do log `ForwardedEvents` sejam despejados como NDJSON no volume
`wefspool` (montado em `/data/wef-spool` no collector). Ver [`wef.md`](wef.md).

## 5. Build e subida

```bash
docker compose build
docker compose up -d          # migrations rodam via serviço 'migrate'
docker compose ps
```

Produção (limites de recurso, logging rotacionado, sem portas expostas
desnecessárias):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 6. Roteamento no NGINX Proxy Manager

Crie um *Proxy Host* apontando para `frontend:8080` (ou
`host:FRONTEND_PUBLISH_PORT`). Habilite SSL e os headers recomendados em
[`npm.md`](npm.md).

## 7. Validação

```bash
./scripts/healthcheck.sh
curl -k https://<seu-host>/api/v1/health
```

Acesse `https://<seu-host>/` e faça login com um usuário do AD que pertença a um
dos grupos de RBAC configurados.

## 8. (Opcional) Dados de demonstração

```bash
./scripts/seed_demo.sh
```

Insere usuários, bloqueios, alertas e eventos fictícios para conhecer a
interface. **Não use em produção.**

## Estrutura do repositório

```
frontend/    SPA React + TS (Dark Ops/NOC)
backend/     API FastAPI + modelos + migrations Alembic
collector/   Coleta e normalização de eventos
worker/      Celery: correlação, risco, alertas, retenção
infra/       postgres init, prometheus, etc.
docs/        Guias
scripts/     setup, backup, restore, healthcheck, seed
tests/       unitários, integração e segurança
secrets/     Docker Secrets (não versionado)
```
