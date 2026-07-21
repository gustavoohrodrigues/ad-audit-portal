# Notificações e ChatOps (ações ativas)

O portal pode enviar **ações ativas fora do AD** (e-mail, Teams, Slack, Discord
e mensagem Windows `msg` via WinRM). Isso **não altera o Active Directory** —
apenas comunica pessoas/estações. Toda ação exige RBAC, **confirmação explícita**
e é **auditada** (`internal_audit_log` + `notification_deliveries`).

## Arquitetura

- Serviço de providers: `backend/app/services/messaging.py` (`deliver()`).
- Endpoint de ação: `POST /api/v1/users/{id}/notify` (RBAC `investigation:manage`).
- Histórico: `GET /api/v1/notifications/history` e tela **Centro de Notificações**.
- Botão **"Avisar usuário"** na tela do usuário (modal com canal, template,
  justificativa obrigatória, ticket e caixa de confirmação).

## Configuração (.env)

```ini
NOTIFICATIONS_ENABLED=true

# ChatOps por webhook (crie os webhooks nos respectivos apps)
TEAMS_ENABLED=true
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
DISCORD_ENABLED=true
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# E-mail usa o bloco SMTP já existente

# Mensagem Windows (msg) via WinRM — SOMENTE hosts na allowlist
MESSAGE_WINRM_ENABLED=true
MESSAGE_WINRM_ALLOWED_HOSTS=nb-financeiro-07.empresa.local,ws-rh-12.empresa.local
MESSAGE_WINRM_TIMEOUT_SECONDS=10
```

### Como obter os webhooks
- **Teams**: canal → Conectores → *Incoming Webhook* → copie a URL.
- **Slack**: *Incoming Webhooks* no app do workspace → *Add New Webhook*.
- **Discord**: Configurações do canal → Integrações → *Criar Webhook*.

## Mensagem Windows (`msg`)

O provider `winrm` executa `msg * "<texto>"` no host alvo via WinRM. Proteções:
- O host **precisa** estar em `MESSAGE_WINRM_ALLOWED_HOSTS` (allowlist).
- Conteúdo é **sanitizado** (sem caracteres de controle, sem interpolação de
  comando arbitrário).
- Requer `MESSAGE_WINRM_ENABLED=true` e as credenciais WinRM configuradas
  (nunca aparecem em log).

## Aviso automático de expiração de senha (roadmap de ativação)

Variáveis já previstas: `PASSWORD_EXPIRY_NOTICE_DAYS=14,7,3,1` e
`PASSWORD_EXPIRY_NOTIFICATION_CHANNEL=email`. A task diária no `worker`/`beat`
que dispara os avisos usando `password_expires_at` (já calculado no sync) é a
próxima ativação natural — o transporte (`messaging.deliver`) já está pronto.

## Auditoria

Cada envio grava em `notification_deliveries` (canal, alvo, solicitante, perfil,
justificativa, ticket, status, correlation_id, erro sanitizado) e em
`internal_audit_log` (ação `notify`). Falhas retornam mensagem sanitizada, sem
expor segredos.
