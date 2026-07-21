# NGINX Proxy Manager (NPM)

O reverse-proxy interno **foi omitido** — a terminação TLS e o roteamento
externo são feitos pelo seu **NGINX Proxy Manager**. O NPM deve apontar para o
serviço `frontend`, que serve o SPA e faz proxy de `/api` para o `backend`.

## Proxy Host

| Campo | Valor |
|---|---|
| Domain Names | `ad-audit.seudominio.local` |
| Scheme | `http` |
| Forward Hostname/IP | IP do host Docker (ou nome do container `frontend` se o NPM estiver na mesma rede) |
| Forward Port | `FRONTEND_PUBLISH_PORT` (padrão `8088`) |
| Cache Assets | opcional |
| Block Common Exploits | ✅ |
| Websockets Support | ✅ |

> Para colocar o NPM na mesma rede Docker do app, conecte o container do NPM à
> rede `ad-audit-portal_internal` e use `Forward Hostname = frontend`,
> `Forward Port = 8080` (sem publicar porta no host).

## SSL

- Aba **SSL** → *Request a new SSL Certificate* (Let's Encrypt) ou use um
  certificado próprio.
- ✅ **Force SSL**
- ✅ **HTTP/2 Support**
- ✅ **HSTS Enabled** e **HSTS Subdomains** (o app não força HSTS por padrão pois
  o TLS termina no NPM).

## Headers de segurança (aba *Advanced*)

O backend já envia `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy`, `Content-Security-Policy` e `Permissions-Policy`. Reforce no
NPM com o bloco abaixo (aba **Advanced → Custom Nginx Configuration**):

```nginx
# HSTS (TLS termina aqui)
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

# Reforço de cabeçalhos (idempotente com os do app)
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "no-referrer" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

# Limites e timeouts
client_max_body_size 10m;
proxy_read_timeout 120s;

# Rate limiting adicional na borda (opcional; o app também aplica)
# limit_req_zone $binary_remote_addr zone=adaudit:10m rate=10r/s;
```

## Ajustes de cookies

A aplicação usa cookies `httpOnly` + `SameSite` para os tokens. Garanta que:

- `COOKIE_SECURE=true` no `.env` (cookies só por HTTPS).
- `FRONTEND_URL` e `CORS_ALLOWED_ORIGINS` no `.env` batem com o domínio público
  configurado no NPM. Caso contrário o login falhará por CORS/cookie.
- Se usar subdomínio, ajuste `COOKIE_DOMAIN` no `.env`.

## Encaminhamento de IP real

O backend confia em `X-Forwarded-For`/`X-Forwarded-Proto` (uvicorn com
`--proxy-headers --forwarded-allow-ips *`). O NPM já envia esses cabeçalhos, o
que garante IPs corretos na auditoria interna e no rate limiting.

## Health check

Configure o monitor do NPM (ou externo) para `GET /api/v1/health` (200 = vivo) e
`GET /api/v1/readiness` (503 se Postgres/Redis indisponíveis).
