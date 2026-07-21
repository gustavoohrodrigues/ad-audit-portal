#!/usr/bin/env bash
# Manutenção do PostgreSQL (host cron). Complementa a retenção automática do
# worker (diária) executando VACUUM ANALYZE e reportando o tamanho do banco.
# A limpeza por retenção também pode ser disparada pela UI (Capacidade) ou pelo
# worker. Uso:  ./scripts/db-maintenance.sh
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [[ -f .env ]] && . ./.env; set +a

PGU="${POSTGRES_USER:-ad_audit_app}"
PGD="${POSTGRES_DB:-ad_audit}"

echo "[+] Tamanho do banco antes:"
docker compose exec -T postgres psql -U "$PGU" -d "$PGD" -tAc \
  "SELECT pg_size_pretty(pg_database_size(current_database()))"

echo "[+] VACUUM (ANALYZE) nas tabelas de maior rotatividade..."
for tbl in normalized_events internal_audit_log notification_deliveries collection_checkpoints; do
  docker compose exec -T postgres psql -U "$PGU" -d "$PGD" -c "VACUUM (ANALYZE) ${tbl};" >/dev/null 2>&1 \
    && echo "    ok: ${tbl}" || echo "    aviso: ${tbl} (pode não existir)"
done

echo "[+] Tamanho do banco depois:"
docker compose exec -T postgres psql -U "$PGU" -d "$PGD" -tAc \
  "SELECT pg_size_pretty(pg_database_size(current_database()))"

echo "[✓] Manutenção concluída."
