# Backup e Restore

O estado persistente relevante está no **PostgreSQL** (eventos, investigações,
alertas, auditoria interna). Redis é volátil (fila/cache) e não requer backup.

## Backup lógico (pg_dump)

Script pronto: [`scripts/backup.sh`](../scripts/backup.sh)

```bash
./scripts/backup.sh
```

O que faz:

- Executa `pg_dump -Fc` (formato *custom*, comprimido) dentro do container
  `postgres`, lendo credenciais do `.env`.
- Salva em `BACKUP_PATH` (padrão `./backups`) como
  `ad_audit_YYYYMMDD_HHMMSS.dump`.
- Aplica retenção: remove backups mais antigos que `BACKUP_RETENTION_DAYS`
  (padrão 30).

### Comando manual equivalente

```bash
docker compose exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > backups/ad_audit.dump
```

## Agendamento

Defina `BACKUP_SCHEDULE` (cron, padrão `0 2 * * *`) e agende no host via crontab:

```cron
0 2 * * *  cd /opt/ad-audit-portal && ./scripts/backup.sh >> /var/log/ad-audit-backup.log 2>&1
```

> Alternativa: um serviço/sidecar de backup no compose. Mantido como script no
> host para simplicidade e para permitir enviar os dumps a um storage externo.

## Restauração (pg_restore)

Script: [`scripts/restore.sh`](../scripts/restore.sh)

```bash
./scripts/restore.sh backups/ad_audit_20260720_020000.dump
```

Pede confirmação (a operação **sobrescreve** o banco) e executa:

```bash
docker compose exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < arquivo.dump
```

### Restauração em ambiente novo

```bash
./scripts/setup.sh
docker compose up -d postgres
# aguarde o healthcheck do postgres
./scripts/restore.sh caminho/arquivo.dump
docker compose up -d
```

## Volumes Docker

Os dados vivem no volume nomeado `pgdata`. Para backup a nível de volume
(além do lógico):

```bash
docker run --rm -v ad-audit-portal_pgdata:/data -v "$PWD/backups":/backup \
  alpine tar czf /backup/pgdata_$(date +%F).tar.gz -C /data .
```

## Boas práticas

- Guarde os dumps **fora do host** (S3/NFS) e criptografados.
- Teste a restauração periodicamente em ambiente de staging.
- Faça backup do `.env` e de `secrets/` em cofre seguro (Vault/1Password) —
  sem eles, chaves e senhas se perdem.
- Antes de atualizar versão, faça um backup (ver [`upgrade.md`](upgrade.md)).
