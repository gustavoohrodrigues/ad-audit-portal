#!/usr/bin/env bash
# Backup lógico do PostgreSQL via pg_dump (formato custom, comprimido).
# Uso: scripts/backup.sh  (lê variáveis do .env)
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [[ -f .env ]] && . ./.env; set +a

BACKUP_DIR="${BACKUP_PATH:-./backups}"
RETENTION="${BACKUP_RETENTION_DAYS:-30}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/ad_audit_${STAMP}.dump"

mkdir -p "$BACKUP_DIR"
echo "[+] Gerando backup em ${OUT}..."

# executa pg_dump dentro do container postgres
docker compose exec -T postgres \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc \
  > "$OUT"

echo "[+] Backup concluído ($(du -h "$OUT" | cut -f1))."

# expurga backups antigos
find "$BACKUP_DIR" -name 'ad_audit_*.dump' -mtime "+${RETENTION}" -print -delete || true
echo "[✓] Retenção aplicada (> ${RETENTION} dias removidos)."
