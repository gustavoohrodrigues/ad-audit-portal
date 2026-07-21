#!/usr/bin/env bash
# Verificação de saúde da stack: containers, readiness do backend, fontes.
set -uo pipefail
cd "$(dirname "$0")/.."

echo "== Containers =="
docker compose ps

echo; echo "== Backend readiness =="
docker compose exec -T backend python -c "
import urllib.request, json
try:
    r = urllib.request.urlopen('http://127.0.0.1:8000/api/v1/readiness')
    print(r.status, r.read().decode())
except Exception as e:
    print('ERRO', e)
"

echo; echo "== Redis =="
docker compose exec -T redis sh -c 'redis-cli -a "$REDIS_PASSWORD" ping' 2>/dev/null || echo "Redis indisponível"

echo; echo "== Postgres =="
docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-ad_audit_app}" || echo "Postgres indisponível"
