# Guia de Atualização

## Princípios

- Sempre **faça backup** antes (ver [`backup-restore.md`](backup-restore.md)).
- As migrations de banco rodam pelo serviço `migrate` (Alembic) e são
  **idempotentes** (`alembic upgrade head`).
- Imagens são reconstruídas a partir do código; não há estado dentro dos
  containers de aplicação.

## Passo a passo

```bash
# 1. Backup
./scripts/backup.sh

# 2. Atualizar o código
git fetch --all
git checkout <tag-ou-branch>
git pull

# 3. Revisar mudanças no .env.example
#    (novas variáveis podem ter sido adicionadas)
diff <(grep -oP '^[A-Z_]+(?==)' .env.example | sort) \
     <(grep -oP '^[A-Z_]+(?==)' .env | sort)
#    Adicione ao seu .env as variáveis novas que aparecerem.

# 4. Rebuild
docker compose build

# 5. Aplicar migrations + subir
docker compose up -d
#    O serviço 'migrate' executa 'alembic upgrade head' antes do backend subir.

# 6. Verificar
./scripts/healthcheck.sh
docker compose logs -f migrate backend
```

## Migrations

Para inspecionar o estado das migrations:

```bash
docker compose run --rm backend alembic current
docker compose run --rm backend alembic history
```

Ao desenvolver novas alterações de schema:

```bash
docker compose run --rm backend alembic revision --autogenerate -m "descricao"
```

> A migração inicial (`0001_initial`) materializa o modelo declarado em
> `backend/app/models/`. Migrações seguintes devem usar operações explícitas
> geradas pelo autogenerate.

## Rollback

- **Aplicação**: `git checkout <tag-anterior>` + `docker compose build` +
  `docker compose up -d`.
- **Banco**: `docker compose run --rm backend alembic downgrade -1` (se a
  migração suportar downgrade) ou restaure o backup lógico com
  [`scripts/restore.sh`](../scripts/restore.sh).

## Atualização sem downtime (produção)

Com Swarm/K8s, use *rolling update* nos serviços `backend`, `frontend`,
`worker` e `collector`. O `beat` deve permanecer com réplica única. Rode o
*Job* de migrations antes de promover a nova versão do backend.

## Dependências

- Backend/collector/worker: versões fixadas em `requirements.txt`.
- Frontend: `package.json`. Em produção, commite o `package-lock.json` e troque
  `npm install` por `npm ci` no `frontend/Dockerfile`.
- Recomenda-se **Dependabot/Renovate** e scan de imagens (Trivy/Grype) no CI —
  ver [`hardening.md`](hardening.md).
