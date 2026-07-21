#!/usr/bin/env bash
# Restauração de backup lógico (pg_restore). Uso: scripts/restore.sh <arquivo.dump>
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [[ -f .env ]] && . ./.env; set +a

FILE="${1:-}"
[[ -z "$FILE" || ! -f "$FILE" ]] && { echo "Uso: $0 <arquivo.dump>"; exit 1; }

read -r -p "Isto irá SOBRESCREVER o banco '${POSTGRES_DB}'. Continuar? [s/N] " ans
[[ "${ans,,}" == "s" ]] || { echo "Cancelado."; exit 0; }

echo "[+] Restaurando ${FILE}..."
docker compose exec -T postgres \
  pg_restore -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --clean --if-exists --no-owner \
  < "$FILE"
echo "[✓] Restauração concluída."
