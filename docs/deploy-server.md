# Guia de Deploy em Servidor de Aplicação (com storage Ceph)

Como levar o AD Audit Portal para um servidor de produção, mantendo os **dados
persistentes no Ceph** em `/mnt/gv0/ad-audit`.

## Visão geral

Você **copia o projeto** para o servidor (código + compose), recria o `.env` e a
pasta `secrets/` **no servidor** (nunca versionados no Git), e sobe a stack com o
override de storage que aponta os volumes para o Ceph.

Só precisam persistir no Ceph:
- `pgdata` → PostgreSQL (dados)
- `redisdata` → Redis (fila/cache/append-only)
- `wef-spool` → eventos WEF a processar
- `backups` → dumps do `pg_dump`
- `secrets` → certificado da CA do AD, etc.

> ⚠️ **Banco em armazenamento distribuído**: PostgreSQL tem melhor desempenho e
> semântica de `fsync`/lock em **Ceph RBD** (bloco formatado com ext4/xfs e
> montado no servidor) do que em **CephFS**. Se `/mnt/gv0` for CephFS, funciona
> para começar, mas para produção com volume alto prefira RBD para o `pgdata`
> (pode-se manter os demais em CephFS).

---

## 1. Copiar o projeto para o servidor

Opção A — Git (recomendado):
```bash
sudo mkdir -p /opt && cd /opt
git clone <seu-repositorio> ad-audit-portal
cd ad-audit-portal
```

Opção B — cópia direta (sem Git), da sua máquina para o servidor:
```bash
rsync -av --exclude '.git' --exclude 'node_modules' --exclude '.env' \
      --exclude 'secrets/*' ./ usuario@servidor:/opt/ad-audit-portal/
```

> O diretório do **código** pode ficar em `/opt/ad-audit-portal` (disco local do
> servidor). Só os **dados** vão para o Ceph (`/mnt/gv0/ad-audit`). Você não
> precisa colocar o código-fonte no Ceph.

## 2. Preparar o storage no Ceph

Confirme que o Ceph está montado (`mount | grep /mnt/gv0`) e rode:
```bash
sudo ./scripts/prepare-ceph-storage.sh
```
Isso cria `pgdata`, `redisdata`, `wef-spool`, `backups`, `secrets` em
`/mnt/gv0/ad-audit` com as permissões corretas (postgres uid 999, redis uid 999,
collector uid 10002).

## 3. Configurar ambiente e segredos (no servidor)

```bash
./scripts/setup.sh          # gera .env com chaves/senhas fortes
$EDITOR .env                # ajuste AD/LDAP, SMTP, domínio, etc.
```
No `.env`, aponte os backups para o Ceph:
```ini
BACKUP_PATH=/mnt/gv0/ad-audit/backups
```
Coloque o certificado da CA do AD (se usar LDAPS) em:
```
/mnt/gv0/ad-audit/secrets/ad_ca_certificate.pem
```
E faça o compose enxergar esse secret — duas opções:
- **Simples**: copie/symlink para o projeto:
  `ln -s /mnt/gv0/ad-audit/secrets/ad_ca_certificate.pem ./secrets/ad_ca_certificate.pem`
- **Ou** ajuste o caminho do secret no `docker-compose.yml`
  (`secrets.ad_ca_certificate.file`).

## 4. Subir a stack (com storage Ceph)

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.ceph.yml \
  build

docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.ceph.yml \
  up -d
```

> Sempre inclua os **três arquivos** nos comandos (`build`, `up`, `logs`, `down`).
> Para não repetir, exporte:
> ```bash
> export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml:docker-compose.ceph.yml
> docker compose up -d      # já usa os três
> ```

As migrations rodam automaticamente (serviço `migrate`). Confira:
```bash
docker compose ps
./scripts/healthcheck.sh
```

## 5. Reverse proxy (NGINX Proxy Manager)

O portal expõe o `frontend` em `FRONTEND_PUBLISH_PORT` (padrão `8088`). Aponte o
NPM para `IP-do-servidor:8088` com SSL. Ver [`npm.md`](npm.md).

Ajuste no `.env` para o domínio real de produção:
```ini
APP_URL=https://ad-audit.astra-sa.com
FRONTEND_URL=https://ad-audit.astra-sa.com
CORS_ALLOWED_ORIGINS=https://ad-audit.astra-sa.com
COOKIE_SECURE=true            # produção com HTTPS
```

## 6. Backups (no Ceph) e cron

Com `BACKUP_PATH=/mnt/gv0/ad-audit/backups`, agende no host:
```cron
0 2 * * *  cd /opt/ad-audit-portal && COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml:docker-compose.ceph.yml ./scripts/backup.sh >> /var/log/ad-audit-backup.log 2>&1
```
Restore: `./scripts/restore.sh /mnt/gv0/ad-audit/backups/ad_audit_XXXX.dump`.

## 7. Migração de dados de um ambiente existente (opcional)

Se você já tem dados no ambiente atual e quer levá-los ao servidor novo:
```bash
# no ambiente atual
./scripts/backup.sh
scp backups/ad_audit_*.dump usuario@servidor:/mnt/gv0/ad-audit/backups/

# no servidor novo (após subir postgres)
./scripts/restore.sh /mnt/gv0/ad-audit/backups/ad_audit_XXXX.dump
```

---

## Checklist de deploy

- [ ] Ceph montado em `/mnt/gv0` e `prepare-ceph-storage.sh` executado.
- [ ] Código em `/opt/ad-audit-portal`; `.env` e `secrets/` recriados no servidor.
- [ ] `BACKUP_PATH` apontando para o Ceph; CA do AD em `secrets/`.
- [ ] `COMPOSE_FILE` com os 3 arquivos (base + prod + ceph).
- [ ] `docker compose build && up -d`; migrations no `head`.
- [ ] NPM apontando para `:8088`, SSL e `COOKIE_SECURE=true`.
- [ ] `healthcheck.sh` verde; backup agendado.

## Atualizações futuras
```bash
cd /opt/ad-audit-portal
./scripts/backup.sh
git pull                     # ou rsync do novo código
docker compose build         # (COMPOSE_FILE já com os 3)
docker compose up -d
```
> Lembrete: **sempre `build` de todas as imagens antes do `up`** — o serviço
> `migrate` tem imagem própria e um rebuild parcial dessincroniza o Alembic.
