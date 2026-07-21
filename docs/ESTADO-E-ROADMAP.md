# AD Audit Portal — Estado Atual & Roadmap de Funcionalidades

Documento vivo. **Parte 1** descreve tudo que já existe hoje na aplicação.
**Parte 2** lista ideias de evolução, cada uma com o ponto do código onde ela
se "encaixa" — para acelerar futuras implementações.

Última atualização: 2026-07-21.

## ✅ Implementado nas Fases 1–2 (2026-07-21)

- **Detecções defensivas** (`/attack-surface`): Kerberoasting (T1558.003),
  AS-REP Roasting (T1558.004), Stale Admins — ver [`detections.md`](detections.md).
- **Score de Segurança com histórico/tendência**: snapshot diário
  (`security_score_history`/`posture_history`) + gráfico no dashboard.
- **Ações ativas / ChatOps**: `messaging.py` (e-mail/Teams/Slack/Discord/WinRM
  `msg`), `POST /users/{id}/notify` com confirmação+auditoria, Centro de
  Notificações — ver [`chatops.md`](chatops.md).
- **Watchlists** de entidades monitoradas.
- **MFA obrigatório por perfil** (`MFA_REQUIRED_ROLES`) com guard de cadastro.
- **Busca global Ctrl+K** (command palette).
- **Playbook guiado** de investigação de bloqueio (checklist com status).
- **Sync incremental por uSNChanged** (`AD_SYNC_MODE=incremental`, checkpoint por
  DC, full resync manual protegido).
- Normalização de novos Event IDs (4768/4769/4770/4773/4648/4672/4697/7045),
  preparando a coleta WEF.

**Adiado para fase própria:** WEF Bridge real, Relatórios PDF/XLSX, Password
spray (depende do WEF).

---

# PARTE 1 — O que já está implementado

## 1. Arquitetura e serviços (Docker Compose)

| Serviço | Stack | Papel |
|---|---|---|
| `frontend` | React + TS + Vite, nginx não-root | SPA "Crimson Ops" (tema preto/vermelho animado); serve o app e faz proxy `/api` → backend |
| `backend` | Python + FastAPI + SQLModel | API REST, auth LDAP+JWT+MFA, RBAC, LDAP leitura, métricas, agendador de sync |
| `collector` | Python assíncrono | Coleta/normalização de eventos (WEF/WinRM/Elastic/Wazuh/Graylog/Splunk) |
| `worker` | Celery | Correlação, risco, alertas, webhook, GLPI, retenção |
| `beat` | Celery beat | Agendamento das tarefas periódicas |
| `postgres` | PostgreSQL 16 | Dados, com índices para busca rápida |
| `redis` | Redis 7 | Cache, fila Celery, rate limit, revogação de token, trava de sync, mute de health checks |
| `migrate` | Alembic | Migrations (0001 schema; 0002 MFA + expiração de senha) |

Reverse-proxy/TLS externo = **NGINX Proxy Manager** (o portal expõe o frontend na porta `8088`).

## 2. Autenticação e segurança de acesso

- **Login LDAP** (contra o AD via LDAPS/LDAP) → **JWT** (access curto + refresh rotacionado/revogável no Redis) — `app/api/v1/endpoints/auth.py`, `app/core/security.py`.
- **MFA (TOTP)** — cadastro com QR Code, ativação, 8 códigos de backup, login em 2 etapas — `app/services/mfa.py`, tabela `user_mfa`, página `frontend/src/pages/Account.tsx`.
- **RBAC** por grupos do AD → 4 perfis (`viewer`, `helpdesk`, `security_analyst`, `administrator`) — `app/core/rbac.py` (mapa em `.env`).
- **Auditoria interna** de login, logout, acesso a JSON bruto, exportações, MFA, notas — tabela `internal_audit_log`, `app/services/audit.py`.
- Rate limiting, headers de segurança, redação de segredos nos logs, cookies httpOnly.

## 3. Sincronização do Active Directory (somente leitura)

- **Usuários (1.243), grupos (3.213), computadores (1.147)** sincronizados — `app/services/ad_sync.py`.
- Agendador automático a cada 60 min (trava no Redis) — `app/services/scheduler.py`; e sob demanda via `POST /admin/sync/ad-users` ou botão na Central de Integrações.
- Conversão de atributos AD (FILETIME/SID/GUID/UAC) — `app/ldap/converters.py`.
- **Expiração de senha** calculada a partir do `maxPwdAge` do domínio → `password_expires_at`.

## 4. Módulos da interface

| Página | O que faz |
|---|---|
| **Dashboard** | Hero animado, **Score de Segurança do AD** (medidor radial), KPIs com count-up, gráfico de falhas de auth, exposição de contas, rankings, saúde dos DCs |
| **Saúde** | Painel estilo Ceph: status geral `HEALTH_OK/WARN/ERR` + lista de health checks com silenciar/reativar |
| **Postura de Segurança** | Cards de risco clicáveis (drill-down): inativas, senha nunca expira, Password Not Required, privilegiadas, SPN, delegação, SIDHistory, adminCount, expiradas-ativas, etc. |
| **Usuários** | Busca (sAM, nome, e-mail, UPN, SID, DN); tela do usuário com timeline, risco, **origem de bloqueio (4740)** e badge de **senha prestes a expirar** |
| **Grupos** | Lista/filtra grupos, destaque de privilegiados, visualização de membros |
| **Computadores** | Inventário + **gráfico de SO clicável** (filtra a lista), alerta de SO legado |
| **Bloqueios** | Investigação de 4740 com correlação, hipóteses técnicas, notas e ticket |
| **Eventos** | Consulta/filtro de eventos normalizados; JSON bruto restrito e auditado |
| **Alertas** | Alertas do motor de risco |
| **Relatórios** | Exportação CSV (bloqueios, senha, grupos privilegiados, eventos) |
| **Integrações** | Cards de status + **testar conexão** (LDAP/SMTP/Webhook/GLPI/Prometheus) + sincronizar AD; ganchos de roadmap Teams/Slack/Discord |
| **Admin** | Fontes de eventos, auditoria interna, retenção |
| **Minha Conta** | Gestão de MFA |
| **Sino de notificações** | Badge com `HEALTH_*` + dropdown com health checks e alertas críticos |

## 5. Coleta, correlação e risco

- **Normalização** de ~23 Event IDs (4624/4625/4740/4724/4728…) — `collector/app/normalizer.py`.
- **Deduplicação** por `(DC, EventRecordID, EventID)` + checkpoint por fonte.
- **Correlação** de bloqueios ↔ falhas (4625/4771/4776) — `worker/app/tasks/correlation.py`.
- **Score de risco 0–100** por evento e **Score de Segurança do AD** (nota A–F) — `worker/app/scoring.py`, `app/services/risk.py`, endpoint `/dashboard/security-score`.
- **Motor de health checks** estilo Ceph (inclui detecção de Kerberoasting) — `app/services/health.py`.
- **Alertas** com deduplicação/supressão, e-mail/webhook/GLPI — `worker/app/tasks/alerts.py`.
- **Retenção/expurgo** automático (LGPD) — `worker/app/tasks/retention.py`.

## 6. Observabilidade e operação

- Métricas Prometheus (`/api/v1/metrics`), health/readiness, logs JSON.
- Scripts: `setup.sh`, `backup.sh`, `restore.sh`, `healthcheck.sh`, `seed_demo.sh`.
- CI (testes + scan Trivy) e Dependabot. **40 testes** (unit + integração + segurança), incluindo garantia de que nenhum endpoint escreve no AD.

---

# PARTE 2 — Roadmap de funcionalidades futuras

Cada item traz **o quê**, **por quê** e **onde encaixar** no código atual.

## A. Comunicação e notificação com usuários  ⭐ (inclui o seu exemplo)

### A1. Disparar mensagens para usuários — `msg *` / broadcast
- **O quê:** enviar uma mensagem a um usuário ou a estações (ex.: "Sua senha
  expira amanhã", "Detectamos bloqueios na sua conta"). Base: comando Windows
  `msg` (`msg <usuario> /server:<host> "texto"` ou `msg * "texto"`), executado
  via WinRM no host alvo; alternativas: e-mail ao usuário, Teams/Slack/Discord.
- **Por quê:** fecha o ciclo — o portal detecta o problema e **avisa** o usuário
  ou o técnico, reduzindo tempo de resposta.
- **Onde encaixar:**
  - Reaproveitar o transporte WinRM já existente em `collector/app/connectors/winrm_conn.py` (mover para um serviço `app/services/messaging.py`).
  - Novo endpoint `POST /api/v1/users/{id}/notify` (RBAC: `security_analyst`/`administrator`, auditado).
  - Botão "Avisar usuário" na tela do usuário e no painel de bloqueio.
  - ⚠️ Isto é **ação ativa** (não fere o "somente leitura no AD", pois não altera
    objetos do AD — apenas envia mensagem ao SO). Exigir confirmação + auditoria.

### A2. Push de alertas de saúde para o chat
- **O quê:** quando o status vira `HEALTH_ERR` (ou surge um check novo), enviar
  card para Teams/Slack/Discord.
- **Onde encaixar:** nova task `worker/app/tasks/monitoring.py` no `beat`, que
  chama `app/services/health.py` (via SQL espelhado) e usa `_dispatch` de
  `worker/app/tasks/alerts.py` (webhook já pronto). Cards de roadmap já existem
  na página **Integrações**.

### A3. Aviso automático de senha a expirar
- **O quê:** e-mail/mensagem automática N dias antes (`password_expires_at` já
  é calculado). **Onde:** task diária no `beat` + SMTP existente.

### A4. Notificar analista em evento crítico
- Alteração em grupo privilegiado, criação de conta admin, reset de senha
  privilegiada → notificação imediata (regras de risco já classificam isso).

## B. Coleta de eventos reais (WEF) — prioridade alta
- Popular Bloqueios/Alertas/Timeline/dashboard com eventos reais. Guias prontos
  em `docs/wef.md` e `docs/gpo-audit.md`; o `collector` já consome NDJSON do
  volume `wefspool`. Só falta a configuração no lado Windows.

## C. Segurança ofensiva/defensiva avançada
- **C1. Kerberoasting/AS-REP roasting** detalhado: listar contas com SPN e sem
  pré-autenticação, com "risco de crack". Base: já detectamos SPN em `health.py`.
- **C2. Password spray**: correlacionar muitos 4625/4771 de origens distintas
  para poucas contas → alerta. **Onde:** nova regra em `worker/app/tasks/correlation.py`.
- **C3. Caminhos de ataque (mini-BloodHound)**: grafo de quem chega a Domain
  Admins via aninhamento de grupos (dados de `ad_groups.members` já sincronizados).
- **C4. Golden/Silver Ticket & anomalias Kerberos** (4769 incomuns).
- **C5. Contas com senha antiga demais / nunca trocada** (`pwd_last_set`).
- **C6. Detecção de contas "stale admin"** (privilegiada + inativa) — cruzamento
  já possível com os flags de `ad_users`.

## D. Histórico e tendências
- **D1. Histórico do Security Score**: snapshot diário → gráfico de tendência no
  hero do dashboard. **Onde:** nova tabela `score_history` + task diária + endpoint.
- **D2. Diff de membros de grupos privilegiados** ao longo do tempo (quem entrou/saiu).
- **D3. Linha do tempo de postura** (contas de risco por dia).

## E. Automação e ITSM
- **E1. Ticket GLPI automático** ao piorar a saúde (fluxo GLPI já implementado em
  `worker/app/tasks/alerts.py`).
- **E2. Playbooks de investigação** de bloqueio (passo-a-passo guiado na UI).
- **E3. Webhooks bidirecionais** (receber ack/close de sistemas externos).

## F. Relatórios
- **F1. Relatório executivo em PDF** (postura + score + top riscos).
- **F2. Agendamento** de relatórios por e-mail (diário/semanal) via `beat`.
- **F3. Mais formatos/filtros** no `reports.py` (hoje CSV).

## G. Sincronização ampliada
- **G1. Sync incremental** por `uSNChanged` (performance em domínios grandes).
- **G2. OUs, GPOs, trusts** e política de senha detalhada.
- **G3. Multi-domínio / multi-floresta** (hoje 1 domínio).

## H. Experiência e operação
- **H1. Busca global (command palette)** — Ctrl+K para achar usuário/grupo/máquina.
- **H2. Watchlist/favoritos** de contas críticas monitoradas.
- **H3. Temas** (o CSS já é baseado em variáveis; fácil adicionar claro/alternativos).
- **H4. Internacionalização** (pt-BR/en).
- **H5. Exibir sessões ativas** e permitir revogar (refresh tokens no Redis).

## I. Segurança da própria aplicação
- **I1. MFA obrigatório por perfil** (ex.: exigir para `administrator`/`security_analyst`).
- **I2. SSO OIDC/SAML** (o `.env` já prevê `AUTH_PROVIDER`).
- **I3. Rate limit por usuário** e bloqueio progressivo de brute force no login.
- **I4. Segregação de leitura de PII** com mascaramento por perfil (LGPD).

## J. Observabilidade
- **J1. Dashboards Grafana** prontos (pasta `infra/grafana`).
- **J2. Regras de alerta Prometheus** já esboçadas em `infra/prometheus/prometheus.yml`.
- **J3. Tracing** (OpenTelemetry) no backend.

---

## Como priorizar (sugestão)
1. **WEF real** (B) — desbloqueia metade das telas com dados vivos.
2. **Push de alertas no chat** (A2) + **avisar usuário** (A1) — fecha o ciclo operacional.
3. **Histórico de score** (D1) — valor executivo imediato.
4. **Password spray & Kerberoasting** (C1/C2) — ganho de segurança alto.

> Convenção para novas ações "ativas" (que enviam algo ou tocam o SO): sempre
> **auditar** (`app/services/audit.py`), exigir **RBAC** adequado e **confirmação**
> na UI, mantendo o princípio de **nunca alterar objetos do AD**.
