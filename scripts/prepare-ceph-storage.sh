#!/usr/bin/env bash
# Prepara a estrutura de diretórios persistentes no armazenamento Ceph.
# Rode UMA VEZ no servidor, antes do primeiro 'docker compose up'.
#
#   sudo ./scripts/prepare-ceph-storage.sh
#
# Ajuste BASE se o ponto de montagem for diferente.
set -euo pipefail

BASE="${AD_AUDIT_STORAGE_BASE:-/mnt/gv0/ad-audit}"

echo "[+] Preparando estrutura em: ${BASE}"

# 0) o ponto de montagem precisa existir/estar montado
if ! mountpoint -q "$(dirname "$BASE")" 2>/dev/null && [ ! -d "$(dirname "$BASE")" ]; then
  echo "[!] ATENÇÃO: $(dirname "$BASE") não parece estar montado. Confirme o mount do Ceph antes de continuar."
fi

mkdir -p \
  "${BASE}/pgdata" \
  "${BASE}/redisdata" \
  "${BASE}/wef-spool" \
  "${BASE}/backups" \
  "${BASE}/secrets"

# 1) PostgreSQL (imagem oficial roda como uid 999 'postgres' e faz chown no init,
#    mas garantimos permissão de dono para o init funcionar em bind mount).
chown -R 999:999 "${BASE}/pgdata" 2>/dev/null || echo "[!] não consegui chown pgdata (rode como root)"
chmod 700 "${BASE}/pgdata" || true

# 2) Redis (imagem roda como uid 999 'redis').
chown -R 999:999 "${BASE}/redisdata" 2>/dev/null || true

# 3) Spool WEF — o collector roda como uid 10002 e precisa escrever/mover arquivos.
chown -R 10002:10002 "${BASE}/wef-spool" 2>/dev/null || true

# 4) Backups e secrets — restritos.
chmod 750 "${BASE}/backups" || true
chmod 700 "${BASE}/secrets" || true

echo "[✓] Estrutura pronta:"
ls -la "${BASE}"
echo
echo "Próximos passos:"
echo "  1) Copie o certificado da CA do AD para ${BASE}/secrets/ad_ca_certificate.pem (se usar LDAPS)."
echo "  2) Ajuste BACKUP_PATH=${BASE}/backups no .env."
echo "  3) Suba com o override do Ceph (ver docs/deploy-server.md)."
