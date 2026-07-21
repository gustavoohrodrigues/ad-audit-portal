#!/usr/bin/env bash
# Popula o banco com dados MOCK para demonstração (NÃO usar em produção).
set -euo pipefail
cd "$(dirname "$0")/.."
echo "[+] Inserindo dados de demonstração..."
docker compose run --rm backend python -m app.seed_mock
echo "[✓] Dados de demonstração inseridos. Acesse o dashboard."
