# Observabilidade — Prometheus e Zabbix

O backend do AD Audit Portal expõe métricas no formato **Prometheus** em `/api/v1/metrics` e pode enviar valores ao **Zabbix** via **trapper** (`zabbix_sender`). Este guia cobre o scrape do Prometheus, o significado das métricas, alertas recomendados e a configuração do Zabbix.

---

## 1. Endpoint de métricas

```
GET https://portal.empresa.local/api/v1/metrics
```

Formato: exposição Prometheus (text/plain; `# HELP` / `# TYPE`). Proteja o acesso (rede interna, allowlist do Prometheus, ou token) — as métricas revelam volumetria de segurança.

---

## 2. Métricas expostas

| Métrica | Tipo | Descrição |
|---|---|---|
| `adaudit_http_requests_total` | counter | Total de requisições HTTP à API (rotule por método/rota/status) |
| `adaudit_login_attempts_total` | counter | Tentativas de login no portal (rótulo `result=success\|failed`) |
| `adaudit_raw_event_access_total` | counter | Acessos a eventos brutos (dado sensível; monitorar para LGPD/auditoria) |
| `adaudit_alerts_active` | gauge | Alertas atualmente ativos (rótulo por severidade) |
| `adaudit_source_up` | gauge | Saúde da fonte de coleta por DC/conector (`1`=up, `0`=down) |
| `adaudit_ingestion_lag_seconds` | gauge | Atraso de ingestão de eventos, em segundos (por DC/fonte) |

> `adaudit_source_up` e `adaudit_ingestion_lag_seconds` alimentam o dashboard de Domain Controllers (ver `wef.md`).

---

## 3. `scrape_config` do Prometheus

Adicione ao `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'ad-audit-portal'
    metrics_path: /api/v1/metrics
    scheme: https
    scrape_interval: 30s
    scrape_timeout: 10s
    # Se o endpoint exigir token/allowlist, use um dos mecanismos abaixo:
    # authorization:
    #   type: Bearer
    #   credentials_file: /etc/prometheus/adaudit_token
    tls_config:
      # ca_file: /etc/prometheus/empresa-ca.pem
      insecure_skip_verify: false
    static_configs:
      - targets: ['portal.empresa.local:443']
        labels:
          app: ad-audit-portal
          env: prod
```

Valide o alvo em **Status → Targets** no Prometheus (deve aparecer `UP`).

---

## 4. Regras de alerta (Prometheus)

Arquivo `adaudit-alerts.yml` (referenciado em `rule_files:` do Prometheus):

```yaml
groups:
  - name: ad-audit-portal
    rules:

      # Atraso de ingestão alto (coleta atrasada em algum DC/fonte)
      - alert: ADAuditIngestionLagHigh
        expr: adaudit_ingestion_lag_seconds > 300
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Atraso de ingestao alto ({{ $labels.source }})"
          description: "Lag de {{ $value | humanizeDuration }} na fonte {{ $labels.source }} ha mais de 5 min."

      # Fonte de eventos indisponível (DC/conector down)
      - alert: ADAuditSourceDown
        expr: adaudit_source_up == 0
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "Fonte de eventos DOWN ({{ $labels.source }})"
          description: "A fonte {{ $labels.source }} nao reporta eventos ha mais de 3 min."

      # Endpoint de métricas / backend inacessível
      - alert: ADAuditBackendDown
        expr: up{job="ad-audit-portal"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Backend do AD Audit Portal inacessivel"
          description: "O Prometheus nao consegue coletar /api/v1/metrics."

      # Pico de falhas de login (possível brute force contra o portal)
      - alert: ADAuditLoginFailuresSpike
        expr: sum(rate(adaudit_login_attempts_total{result="failed"}[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Pico de falhas de login no portal"
          description: "Taxa elevada de logins falhos ({{ $value | printf \"%.2f\" }}/s) nos ultimos 5 min."

      # Muitos alertas críticos ativos simultaneamente
      - alert: ADAuditCriticalAlertsActive
        expr: sum(adaudit_alerts_active{severity="critical"}) > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Alertas CRITICOS ativos no AD Audit"
          description: "{{ $value }} alerta(s) critico(s) ativo(s) no portal."
```

Ajuste os limiares (`> 300`, `> 1`) à realidade do ambiente. Para o lag, alinhe com a criticidade da janela de detecção de bloqueios (evento 4740).

---

## 5. Zabbix (trapper)

Além do Prometheus, o portal pode **enviar** valores ao Zabbix via itens do tipo **Zabbix trapper**.

### 5.1 Variáveis do `.env`

```dotenv
ZABBIX_ENABLED=true
ZABBIX_SERVER=zabbix.empresa.local
ZABBIX_HOST=ad-audit-portal          # nome do host cadastrado no Zabbix
ZABBIX_TRAPPER_PORT=10051
```

### 5.2 Cadastro no Zabbix

1. Crie um **Host** no Zabbix com o nome igual a `ZABBIX_HOST` (`ad-audit-portal`).
2. Para cada métrica, crie um **Item** do tipo **Zabbix trapper** com a **key** correspondente.
3. (Opcional) Crie **Triggers** sobre esses itens.

### 5.3 Itens sugeridos

| Item (nome) | Key (trapper) | Tipo | Observação |
|---|---|---|---|
| Ingestion lag | `adaudit.ingestion.lag` | Numeric (float) | segundos; trigger `>300` |
| Source up | `adaudit.source.up` | Numeric (unsigned) | 1/0; trigger `=0` |
| Alertas ativos (crítico) | `adaudit.alerts.active.critical` | Numeric (unsigned) | trigger `>0` |
| Logins falhos (taxa) | `adaudit.login.failed.rate` | Numeric (float) | por minuto |
| Acessos a eventos brutos | `adaudit.raw_event.access` | Numeric (unsigned) | auditoria/LGPD |

### 5.4 Envio manual com `zabbix_sender` (teste)

```bash
zabbix_sender -z zabbix.empresa.local -p 10051 \
  -s "ad-audit-portal" \
  -k adaudit.ingestion.lag -o 42

# Vários valores de uma vez, via arquivo (host key value por linha)
zabbix_sender -z zabbix.empresa.local -p 10051 -i /tmp/adaudit-metrics.txt
```

Exemplo de `/tmp/adaudit-metrics.txt`:

```
"ad-audit-portal" adaudit.source.up 1
"ad-audit-portal" adaudit.alerts.active.critical 0
"ad-audit-portal" adaudit.login.failed.rate 0.3
```

### 5.5 Exemplos de trigger (expressões Zabbix)

```
# Atraso de ingestão alto
last(/ad-audit-portal/adaudit.ingestion.lag) > 300

# Fonte down
last(/ad-audit-portal/adaudit.source.up) = 0

# Alertas críticos ativos
last(/ad-audit-portal/adaudit.alerts.active.critical) > 0
```

---

## 6. Boas práticas

- Não exponha `/api/v1/metrics` publicamente; restrinja à rede de monitoramento (ver `hardening.md`).
- Monitore `adaudit_raw_event_access_total` como indicador de **conformidade/LGPD** (acesso a dados sensíveis deve ser raro e justificado — ver `AUDIT_RAW_EVENT_ACCESS_SECURITY_ONLY` em `hardening.md`).
- Use um único caminho de alerta primário (Prometheus **ou** Zabbix) para o mesmo sinal, evitando alertas duplicados; o outro pode servir de redundância.
