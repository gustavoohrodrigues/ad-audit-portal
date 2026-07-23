# Performance, Escalabilidade e Roadmap de Evolução

Documento da evolução de performance/escala do AD Audit Portal. **Fase 1
(diagnóstico + quick wins) já entregue**; as demais fases estão planejadas.

## ✅ Fase 1 — entregue (2026-07-21)

### Cache Redis (`backend/app/core/cache.py`)
- `get_or_set(namespace, key, ttl, loader)` com TTL, **proteção anti-stampede**
  (lock curto no Redis) e **fallback seguro** ao loader se o Redis falhar.
- Métricas Prometheus: `adaudit_cache_hits_total` / `adaudit_cache_misses_total`
  por namespace.
- Aplicado a **busca global** (`/search`) e **Security Score**; invalidado
  automaticamente após cada sync do AD (`cache.invalidate`).
- TTLs configuráveis por `.env` (`CACHE_*`).

### Índices de banco (migration `0005_perf_indexes`)
- Índices compostos em `normalized_events`: `(event_time_utc DESC, event_id)`,
  `(target_sid, event_time_utc DESC)`, `(target_upn, …)`, `(source_ip, …)`,
  `(risk_score DESC, …)`, `(severity, …)`, `(collector_source, ingested_at DESC)`.
- **Índices parciais** (menores e mais rápidos): bloqueios (4740), falhas de
  autenticação, alvos privilegiados e eventos críticos (`risk_score >= 75`).
- Idempotentes (`CREATE INDEX IF NOT EXISTS`), reversíveis no downgrade.

### Pool e limites (`.env`)
- Pool SQLAlchemy configurável: `API_SQL_POOL_SIZE`, `API_SQL_MAX_OVERFLOW`,
  `API_SQL_POOL_RECYCLE_SECONDS` (+ `pool_pre_ping`).
- Limites: `API_MAX_PAGE_SIZE`, `API_DEFAULT_EVENT_RANGE_DAYS`,
  `API_MAX_EVENT_RANGE_DAYS`.

### Nova página: Capacidade & Performance (`/capacity`, admin)
- Endpoint `GET /api/v1/admin/capacity`: tamanho do banco, **maiores tabelas**
  (tamanho + linhas), contagens das tabelas centrais, **índices sem uso**,
  memória/chaves/hit-ratio do **Redis** e **profundidade das filas Celery**.
- UI com KPIs, tabela de maiores tabelas, filas com backlog e configuração ativa.

### Feature flags
- `FEATURE_INCIDENTS_ENABLED`, `FEATURE_PERFORMANCE_DASHBOARD_ENABLED`,
  `FEATURE_WEBSOCKET_ENABLED`, `FEATURE_PARTITIONING_ENABLED`.

### E-mail (Postfix)
- SMTP configurado: `10.1.1.26:1025` (sem TLS/auth — relay interno). Envio
  validado para os destinatários corporativos via `messaging.deliver`.

## Rollback da Fase 1
- Migração: `alembic downgrade 0004_playbook_usn` (remove os índices).
- Cache: `CACHE_ENABLED=false` desativa sem código.
- Página de capacidade: somente leitura, sem efeito colateral.

---

## Roadmap — próximas fases (planejado)

**Fase 2 — Banco: agregações e particionamento**
- Materialized views / tabelas de agregação incremental (`event_volume_hourly`,
  `lockouts_daily`, `security_posture_daily`, …) com refresh via Celery + lock.
- Particionamento declarativo por RANGE de `event_time_utc` (mensal), criação
  automática de partições futuras e retenção por `DROP PARTITION`.
- Busca com `unaccent` + `pg_trgm` e ranking por relevância.

**Fase 3 — Collector, filas e DLQ**
- Filas Celery dedicadas (`ingestion_high`, `correlation`, `alerts`, `reports`,
  `sync`, `maintenance`), backpressure, batch adaptativo, **DLQ + replay**,
  cadeia de custódia (hash da evidência), painel de qualidade de ingestão.

**Fase 4 — Observabilidade / SLO**
- OpenTelemetry (FastAPI, SQLAlchemy, Redis, Celery, LDAP, HTTP) com sampling e
  sem PII; SLOs + alertas de burn-rate; dashboards Grafana em `infra/grafana/`.

**Fase 5 — SOC/SIEM/NOC**
- Módulo `incidents`; adaptadores Sentinel/Wazuh/Elastic/Splunk/TheHive/MISP;
  template Zabbix + LLD; centro de runbooks versionados.

**Fase 6 — Relatórios e UI performance**
- Relatórios PDF/XLSX assíncronos com marca d'água, hash SHA-256, links
  assinados e agendamento; code-splitting, virtualização de tabelas, SSE/WebSocket
  para health/notificações/progresso.

**Fase 7 — Backup, DR e testes de carga**
- PITR (pgBackRest/WAL-G), backup criptografado offsite, teste de restore
  automatizado, benchmarks de ingestão (10k/100k/1M eventos) e carga da API.

> Dependência crítica de várias fases: a **coleta WEF real** (eventos vivos).
> Priorizar a integridade do dado antes de dashboards dependentes de eventos.

---

## Controle de volume do banco (anti-crescimento descontrolado)

Em ambientes com muito tráfego de autenticação, `normalized_events` domina o
tamanho do banco. Três mecanismos evitam o crescimento insustentável:

1. **Não gravar o JSON bruto de eventos de ruído** (`EVENT_STORE_RAW=false`). O
   `raw_event_json` (≈2 KB/linha, vai para TOAST) é o maior consumidor. Só é
   preservado para os tipos importantes de `EVENT_STORE_RAW_TYPES` (bloqueios,
   trocas/resets de senha, mudanças de grupo, criação/exclusão de conta,
   serviços instalados, mudanças no DS). O restante grava `{}`.

2. **Descartar tipos de puro volume na ingestão** (`EVENT_DROP_TYPES`). Por
   padrão, `successful_logon` (4624) — o maior gerador de volume em DCs e sem
   consumidor no portal — não é sequer buscado nem gravado.

3. **Retenção curta para ruído** (`EVENT_NOISE_RETENTION_DAYS`, padrão 14d). Os
   eventos de autenticação de alto volume (`EVENT_NOISE_TYPES`) são expurgados
   bem antes dos demais (`EVENT_RETENTION_DAYS`, padrão 90d). O expurgo roda no
   worker diariamente, em lotes (`ctid`), sem travar a base.

Complementos de performance:

- **Ingestão em `executemany`** (um `INSERT` por lote em vez de linha a linha) —
  elimina o gargalo/travamento sob alto volume.
- **Autovacuum agressivo** em `normalized_events` (migration `0010`) evita bloat
  de linhas mortas — principal causa de lentidão progressiva.
- **Índice BRIN** em `event_time_utc` para varreduras por período eficientes.
- Para encolher o arquivo já inchado, use **Capacidade → Recuperar espaço
  (VACUUM FULL)** após o primeiro expurgo.

> Ajuste fino: se precisar reduzir ainda mais, baixe `EVENT_NOISE_RETENTION_DAYS`
> (ex.: 7) e mantenha `EVENT_STORE_RAW=false`. Para voltar a guardar 4624,
> remova-o de `EVENT_DROP_TYPES` e reative o ID nos conectores.
