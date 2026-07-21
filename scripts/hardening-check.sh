#!/usr/bin/env bash
# Verificação de hardening da stack. Executa checagens de segurança e imprime
# um relatório PASS/WARN/FAIL. Não altera nada.
set -uo pipefail
cd "$(dirname "$0")/.."

pass() { echo "  [PASS] $1"; }
warn() { echo "  [WARN] $1"; }
fail() { echo "  [FAIL] $1"; }

echo "== Hardening check — AD Audit Portal =="

echo "1) Containers rodando como não-root"
for svc in backend collector worker frontend; do
  cid=$(docker compose ps -q "$svc" 2>/dev/null)
  [ -z "$cid" ] && { warn "$svc não está em execução"; continue; }
  uid=$(docker inspect -f '{{.Config.User}}' "$cid" 2>/dev/null)
  if [ -n "$uid" ] && [ "$uid" != "0" ] && [ "$uid" != "root" ]; then
    pass "$svc roda como usuário '$uid'"
  else
    warn "$svc pode estar rodando como root (User='$uid')"
  fi
done

echo "2) no-new-privileges"
for svc in backend frontend; do
  cid=$(docker compose ps -q "$svc" 2>/dev/null)
  [ -z "$cid" ] && continue
  if docker inspect -f '{{.HostConfig.SecurityOpt}}' "$cid" 2>/dev/null | grep -q "no-new-privileges"; then
    pass "$svc com no-new-privileges"
  else
    warn "$svc sem no-new-privileges (use docker-compose.hardening.yml)"
  fi
done

echo "3) Cabeçalhos de segurança (via frontend)"
port="${FRONTEND_PUBLISH_PORT:-8088}"
hdrs=$(curl -s -D - -o /dev/null "http://localhost:${port}/api/v1/health" 2>/dev/null)
for h in "X-Content-Type-Options" "X-Frame-Options" "Content-Security-Policy" "Referrer-Policy"; do
  echo "$hdrs" | grep -qi "$h" && pass "header $h presente" || warn "header $h ausente"
done

echo "4) Banco: statement_timeout ativo"
st=$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-ad_audit_app}" -d "${POSTGRES_DB:-ad_audit}" -tAc "SHOW statement_timeout" 2>/dev/null)
[ -n "$st" ] && [ "$st" != "0" ] && pass "statement_timeout=$st" || warn "statement_timeout não definido no servidor (definido por sessão no app)"

echo "5) Segredos e configuração"
[ -f .env ] && { perm=$(stat -c '%a' .env 2>/dev/null); [ "$perm" = "600" ] || [ "$perm" = "640" ] && pass ".env com permissão $perm" || warn ".env com permissão $perm (recomendado 600)"; }
grep -q "^APP_DEBUG=false" .env 2>/dev/null && pass "APP_DEBUG=false" || warn "APP_DEBUG deveria ser false em produção"
grep -q "^COOKIE_SECURE=true" .env 2>/dev/null && pass "COOKIE_SECURE=true" || warn "COOKIE_SECURE=false (ok só em lab HTTP; true em produção HTTPS)"
grep -qE "^(AD_LDAP_URI=ldaps://|AD_LDAP_TLS_VERIFY=true)" .env 2>/dev/null && pass "LDAPS/validação de certificado presente" || warn "LDAP em texto puro (habilite LDAPS em produção)"

echo "6) Portas expostas"
docker compose ps --format '{{.Service}} {{.Ports}}' 2>/dev/null | grep -vE "frontend|NAME" | grep -qE "0.0.0.0|:::" \
  && warn "há serviços com porta publicada além do frontend (revise)" \
  || pass "somente o frontend publica porta"

echo "== fim =="
