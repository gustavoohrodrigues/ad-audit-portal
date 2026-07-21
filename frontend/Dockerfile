# syntax=docker/dockerfile:1
# ============ Stage 1: build do SPA ============
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json ./
# usa npm install (sem lockfile versionado neste template); em produção,
# commite o package-lock.json e troque para `npm ci`.
RUN npm install
COPY . .
RUN npm run build

# ============ Stage 2: nginx não-root servindo estáticos ============
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=4s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
