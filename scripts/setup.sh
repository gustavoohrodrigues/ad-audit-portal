#!/usr/bin/env bash
# Prepara o ambiente: gera .env a partir do .env.example com chaves fortes e
# cria placeholders necessários. Idempotente — não sobrescreve .env existente.
set -euo pipefail
cd "$(dirname "$0")/.."

gen() { openssl rand -hex 48; }
genpw() { openssl rand -base64 24 | tr -d '/+=' | head -c 28; }

if [[ -f .env ]]; then
  echo "[=] .env já existe — não será sobrescrito."
else
  echo "[+] Gerando .env a partir de .env.example..."
  cp .env.example .env
  APP_KEY=$(gen); JWT_KEY=$(gen); PG_PW=$(genpw); RD_PW=$(genpw)

  # substituições seguras (usa | como delimitador)
  sed -i "s|APP_SECRET_KEY=.*|APP_SECRET_KEY=${APP_KEY}|" .env
  sed -i "s|JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT_KEY}|" .env
  sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PW}|" .env
  sed -i "s|REDIS_PASSWORD=.*|REDIS_PASSWORD=${RD_PW}|" .env
  sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://ad_audit_app:${PG_PW}@postgres:5432/ad_audit|" .env
  sed -i "s|REDIS_URL=.*|REDIS_URL=redis://:${RD_PW}@redis:6379/0|" .env
  sed -i "s|CELERY_BROKER_URL=.*|CELERY_BROKER_URL=redis://:${RD_PW}@redis:6379/1|" .env
  sed -i "s|CELERY_RESULT_BACKEND=.*|CELERY_RESULT_BACKEND=redis://:${RD_PW}@redis:6379/2|" .env
  echo "[+] .env criado com segredos aleatórios. Ajuste os parâmetros do AD/LDAP!"
fi

# placeholder de certificado CA (para não quebrar o Docker Secret em laboratório)
if [[ ! -f secrets/ad_ca_certificate.pem ]]; then
  echo "[!] secrets/ad_ca_certificate.pem ausente — criando placeholder vazio."
  echo "    Em produção substitua pelo certificado real e mantenha AD_LDAP_TLS_VERIFY=true."
  : > secrets/ad_ca_certificate.pem
fi

echo "[✓] Setup concluído. Próximo passo: docker compose build && docker compose up -d"
