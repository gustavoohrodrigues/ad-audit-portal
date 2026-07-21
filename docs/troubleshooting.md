# Solução de Problemas (Troubleshooting)

## O backend não sobe

O backend **recusa iniciar** se faltar configuração obrigatória — isso é
proposital. A mensagem indica exatamente o que corrigir:

```
RuntimeError: Configuração incompleta. As seguintes variáveis de ambiente
OBRIGATÓRIAS estão ausentes: DATABASE_URL. Copie .env.example para .env...
```

Variáveis obrigatórias: `APP_SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`,
`REDIS_URL`. Além disso, com `AD_ENABLED=true` e `AUTH_PROVIDER=ldap` são
exigidas `AD_LDAP_URI`, `AD_BIND_USERNAME`, `AD_BIND_PASSWORD`, `AD_BASE_DN`.

```
Value error, chave contém valor de placeholder
```
→ Você deixou `APP_SECRET_KEY`/`JWT_SECRET_KEY` com o texto `GERAR...`. Gere:
`openssl rand -hex 48`. O `./scripts/setup.sh` faz isso automaticamente.

```bash
docker compose logs backend
docker compose logs migrate
```

## Falha de login

| Sintoma | Causa provável | Ação |
|---|---|---|
| `401 Credenciais inválidas` | usuário/senha errados ou bind falhou | teste o LDAPS (abaixo) |
| `403 Usuário sem grupo de autorização` | usuário não está em nenhum grupo RBAC | adicione-o a um dos grupos `AUTH_GROUP_*` |
| Login "gira" e volta | CORS/cookie | confira `FRONTEND_URL`/`CORS_ALLOWED_ORIGINS` e `COOKIE_SECURE` (ver [`npm.md`](npm.md)) |

## LDAPS não conecta

Teste dentro do container do backend:

```bash
docker compose exec backend python -c "
from app.ldap.client import ReadOnlyLDAP
ok, msg = ReadOnlyLDAP().test_connection()
print(ok, msg)
"
```

Ou via API (como administrator):

```bash
curl -X POST https://<host>/api/v1/admin/connectors/test \
  -H 'Content-Type: application/json' -b cookies.txt \
  -d '{"connector_type":"ldap"}'
```

Erros comuns:

- **Certificado**: `AD_LDAP_TLS_VERIFY=true` mas `secrets/ad_ca_certificate.pem`
  ausente/errado. Exporte a CA correta (ver [`ldap.md`](ldap.md)). Em
  laboratório, `AD_LDAP_TLS_VERIFY=false` (**nunca em produção**).
- **Porta/host**: valide `AD_LDAP_URI` (636 para LDAPS) e a resolução DNS dos
  DCs a partir do container.
- **Conta bloqueada/expirada**: a conta de serviço deve ter senha que não
  expira e não estar bloqueada.

## Nenhum evento aparece

1. O collector está lendo? `docker compose logs -f collector` — deve mostrar
   `Fonte=... recebidos=... inseridos=...`.
2. O modo está correto? `EVENT_COLLECTOR_MODE=wef`.
3. Os eventos chegam ao spool? Verifique o volume `wefspool`
   (`/data/wef-spool`) — deve conter arquivos `*.ndjson`. Ver [`wef.md`](wef.md).
4. A auditoria está habilitada nos DCs? Ver [`gpo-audit.md`](gpo-audit.md).
5. Saúde das fontes: `GET /api/v1/admin/connectors` e o card de DCs no
   dashboard (status `healthy`/`degraded`/`down`).

## Eventos duplicados

Não deve ocorrer: há índice único `(domain_controller, event_record_id,
event_id)` com `ON CONFLICT DO NOTHING`. Se um DC não envia `EventRecordID`
(fica nulo), a dedup fica mais fraca — confira o exportador NDJSON.

## Risco/alertas não são gerados

- `RISK_SCORING_ENABLED=true` e `ALERTS_ENABLED=true`?
- O `worker` e o `beat` estão rodando? `docker compose ps`.
- `docker compose logs worker beat`.
- Limiares: `RISK_ALERT_THRESHOLD_MEDIUM/HIGH/CRITICAL`.

## GLPI não cria ticket

- Só cria para severidade **crítica** e com `GLPI_ENABLED=true` +
  `GLPI_CREATE_TICKET_ON_CRITICAL=true`.
- Deduplicação: dentro de `GLPI_DEDUP_WINDOW_HOURS` não recria para o mesmo alvo.
- Tokens: valide `GLPI_APP_TOKEN`/`GLPI_USER_TOKEN` (ver [`glpi.md`](glpi.md)).

## readiness retorna 503

`GET /api/v1/readiness` checa Postgres e Redis. Veja qual falhou no corpo da
resposta e confirme os healthchecks:

```bash
docker compose ps
docker compose exec postgres pg_isready -U "$POSTGRES_USER"
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping
```

## Migrations falharam

```bash
docker compose run --rm backend alembic current
docker compose run --rm backend alembic upgrade head
```
Se o banco estiver corrompido/inconsistente em ambiente novo, restaure um
backup (ver [`backup-restore.md`](backup-restore.md)).

## Logs

Todos os serviços emitem **JSON estruturado**. Segredos são redigidos
automaticamente. Para depurar mais:

```ini
APP_DEBUG=true
LOG_LEVEL=DEBUG
LOG_FORMAT=console
```
(reverta em produção).
