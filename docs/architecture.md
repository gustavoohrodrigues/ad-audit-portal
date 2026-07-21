# Arquitetura

O AD Audit Portal é uma stack containerizada, **somente leitura** em relação ao
Active Directory, preparada para evoluir de Docker Compose para Docker Swarm ou
Kubernetes (serviços desacoplados, estado externalizado em Postgres/Redis,
configuração 100% por ambiente).

## Diagrama de componentes

```mermaid
flowchart TB
    subgraph EXT[Infraestrutura existente]
        NPM[NGINX Proxy Manager<br/>TLS + roteamento]
        AD[(Active Directory<br/>Domain Controllers)]
    end

    subgraph STACK[Stack AD Audit Portal]
        FE[frontend<br/>React+TS / nginx :8080]
        BE[backend<br/>FastAPI :8000]
        CO[collector<br/>WEF/SIEM]
        WK[worker<br/>Celery]
        BT[beat<br/>Celery scheduler]
        MG[migrate<br/>Alembic]
        PG[(postgres :5432)]
        RD[(redis :6379)]
    end

    NPM -->|HTTPS| FE
    FE -->|/api| BE
    BE -->|LDAPS leitura| AD
    AD -->|WEF / WinRM / SIEM| CO
    CO --> PG
    BE --> PG
    BE --> RD
    WK --> PG
    WK --> RD
    BT --> RD
    MG --> PG
    WK -->|webhook / GLPI / e-mail| EXT
    BE -->|/metrics| NPM
```

## Fluxo de eventos

```mermaid
sequenceDiagram
    participant DC as Domain Controller
    participant WEF as Windows Event Collector
    participant SP as Spool NDJSON
    participant CO as collector
    participant PG as PostgreSQL
    participant WK as worker (Celery)
    participant UI as frontend

    DC->>WEF: Encaminha log Security (subscription)
    WEF->>SP: Exporta eventos (NDJSON)
    loop A cada EVENT_POLL_INTERVAL_SECONDS
        CO->>SP: Lê lote (checkpoint por fonte)
        CO->>CO: Normaliza (EventID → EventType)
        CO->>PG: INSERT ... ON CONFLICT DO NOTHING<br/>(dedup DC+RecordID+EventID)
        CO->>PG: Atualiza checkpoint + estatísticas da fonte
    end
    loop Tarefas agendadas (beat)
        WK->>PG: Correlaciona 4740 ↔ 4625/4771/4776
        WK->>PG: Calcula risco (0–100) e severidade
        WK->>PG: Gera alertas (dedup + supressão)
        WK->>EXT: Despacha (e-mail/webhook/GLPI se crítico)
        WK->>PG: Aplica retenção/expurgo
    end
    UI->>PG: Consulta via backend (RBAC + auditoria)
```

## Decisões de arquitetura

- **Separação collector/worker/backend**: a coleta é independente da API e do
  processamento; cada uma escala horizontalmente sem afetar as demais.
- **Deduplicação no banco**: o índice único `(domain_controller,
  event_record_id, event_id)` torna a ingestão idempotente — reentregas comuns
  em WEF não geram duplicatas, e o collector pode reprocessar sem risco.
- **Checkpoint por fonte** (`collection_checkpoints`): retoma a coleta do ponto
  correto após reinícios.
- **Estado externalizado**: nenhum serviço guarda estado local relevante; tudo
  vai para Postgres (dados) e Redis (fila/cache/sessão), viabilizando réplicas.
- **Configuração por ambiente** com validação no startup: o backend recusa
  iniciar se faltar variável obrigatória (ver `docs/troubleshooting.md`).
- **Somente leitura no AD**: a API não expõe operação de escrita — garantido por
  teste automatizado.

## Modelo de dados (resumo)

| Tabela | Papel |
|---|---|
| `normalized_events` | Evento canônico (todos os campos + `raw_event_json` JSONB) |
| `ad_users` / `ad_computers` / `ad_groups` | Objetos sincronizados do AD (leitura) |
| `domain_controllers` | Saúde por DC (heartbeat, último evento, lag) |
| `event_sources` | Fontes de coleta e estatísticas |
| `collection_checkpoints` | Retomada de coleta por fonte |
| `lockout_investigations` | Painel de investigação de bloqueio (4740) |
| `alerts` / `risk_rules` | Alertas e regras de risco |
| `ticket_links` / `analyst_notes` | Tickets GLPI e anotações |
| `report_exports` | Registro de exportações |
| `internal_audit_log` | Auditoria interna (login, JSON bruto, export…) |
| `retention_policies` | Política de retenção por tipo de dado |

Migrations em `backend/alembic/`. A migração inicial materializa o modelo
declarado em `backend/app/models/` (fonte única de verdade).

## Evolução para Swarm/Kubernetes

- Trocar `secrets:` de arquivo por *Docker Secrets* (Swarm) ou *Secrets/
  ExternalSecrets* (K8s).
- `frontend`, `backend`, `worker`, `collector` viram Deployments com réplicas;
  `beat` deve ter **réplica única** (scheduler).
- `postgres`/`redis` → serviços gerenciados ou StatefulSets com volumes.
- `migrate` → *Job* de pré-deploy (init container ou Helm hook).
