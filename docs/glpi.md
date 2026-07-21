# Integração com GLPI

O AD Audit Portal integra-se ao **GLPI** para abrir **tickets automaticamente** quando um alerta **CRÍTICO** é gerado, e permite ao analista **vincular manualmente** um ticket a uma investigação de bloqueio de conta. A criação usa a **API REST do GLPI** (`/apirest.php`).

> A integração é **somente saída** para o GLPI (abertura/registro de tickets). Nenhuma ação é executada no Active Directory.

---

## 1. Variáveis do `.env`

| Variável | Descrição |
|---|---|
| `GLPI_ENABLED` | Habilita a integração (`true`/`false`) |
| `GLPI_URL` | URL base do GLPI (sem `/apirest.php`), ex.: `https://glpi.empresa.local` |
| `GLPI_APP_TOKEN` | App-Token do cliente de API |
| `GLPI_USER_TOKEN` | user_token da conta de API |
| `GLPI_ENTITY_ID` | ID da entidade onde o ticket será criado |
| `GLPI_CREATE_TICKET_ON_CRITICAL` | Se `true`, abre ticket automaticamente para alertas CRÍTICOS |
| `GLPI_DEDUP_WINDOW_HOURS` | Janela (horas) de deduplicação para evitar tickets repetidos |

Exemplo:

```dotenv
GLPI_ENABLED=true
GLPI_URL=https://glpi.empresa.local
GLPI_APP_TOKEN=__docker_secret__
GLPI_USER_TOKEN=__docker_secret__
GLPI_ENTITY_ID=0
GLPI_CREATE_TICKET_ON_CRITICAL=true
GLPI_DEDUP_WINDOW_HOURS=6
```

> Trate `GLPI_APP_TOKEN` e `GLPI_USER_TOKEN` como segredos (Docker Secret/Vault — ver `hardening.md`).

---

## 2. Obter o App-Token

O App-Token identifica a **aplicação cliente** que consome a API.

1. No GLPI, habilite a API REST em **Configuração → Geral → API** → marque **"Habilitar API REST"**.
2. Em **Configuração → Geral → API → Clientes de API (API clients)**, crie/edite um cliente (ex.: "AD Audit Portal"), defina o intervalo de IPs permitido (o IP do worker) e copie o **App-Token** gerado.

---

## 3. Obter o user_token

O user_token autentica a **conta de API** (recomenda-se um usuário técnico dedicado, com perfil de mínimo privilégio que possa **criar tickets** na entidade `GLPI_ENTITY_ID`).

1. Crie/escolha um usuário de serviço no GLPI (ex.: `api_adaudit`).
2. Acesse o **perfil desse usuário → aba "Configurações remotas de acesso" (Remote access keys)**.
3. Gere/regenerate o **"Token de API pessoal" (user_token)** e copie o valor.

---

## 4. Comportamento da integração

- **Somente alertas CRÍTICOS** disparam abertura automática de ticket (quando `GLPI_CREATE_TICKET_ON_CRITICAL=true`). Alertas de severidade menor **não** abrem ticket automaticamente.
- **Deduplicação:** dentro da janela `GLPI_DEDUP_WINDOW_HOURS`, alertas equivalentes (mesma conta/tipo/assinatura) **não** geram novo ticket; o alerta é anexado ao ticket já aberto, evitando enxurrada de chamados durante um incidente em curso.
- Após criar o ticket, o worker **registra a URL e o número do ticket** na investigação/alerta correspondente, para rastreabilidade (o analista vê o link para o GLPI direto no portal).

### 4.1 Fluxo de chamadas à API (executado pelo worker)

```text
1. initSession   -> autentica com App-Token + user_token, recebe Session-Token
2. POST Ticket   -> cria o ticket na entidade GLPI_ENTITY_ID
3. killSession   -> encerra a sessão (não deixa sessões penduradas)
```

Exemplo equivalente em `curl` (o worker faz isso programaticamente):

```bash
# 1) initSession — obtém o Session-Token
SESSION=$(curl -sS "$GLPI_URL/apirest.php/initSession" \
  -H "App-Token: $GLPI_APP_TOKEN" \
  -H "Authorization: user_token $GLPI_USER_TOKEN" \
  | jq -r '.session_token')

# 2) POST /Ticket — cria o chamado
curl -sS -X POST "$GLPI_URL/apirest.php/Ticket" \
  -H "App-Token: $GLPI_APP_TOKEN" \
  -H "Session-Token: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{
        "input": {
          "name": "[AD Audit] CRITICO: bloqueio recorrente - jsilva",
          "content": "Alerta critico detectado pelo AD Audit Portal.\nConta: jsilva\nEvento: 4740 (lockout)\nDC: dc01\nOrigem: WKS-1234 (10.0.4.21)\nBloqueios recentes: 5",
          "entities_id": 0,
          "urgency": 5,
          "impact": 4,
          "priority": 5,
          "type": 1,
          "itilcategories_id": 0
        }
      }'

# 3) killSession — encerra a sessão
curl -sS "$GLPI_URL/apirest.php/killSession" \
  -H "App-Token: $GLPI_APP_TOKEN" \
  -H "Session-Token: $SESSION"
```

Resposta de criação (exemplo): `{"id": 4821, "message": "..."}`. O portal monta a URL `https://glpi.empresa.local/front/ticket.form.php?id=4821` e a associa ao alerta.

---

## 5. Vincular manualmente um ticket a uma investigação de bloqueio

Quando o ticket já existe (aberto manualmente ou por outro fluxo), o analista pode vinculá-lo a uma investigação de bloqueio (evento 4740) pelo endpoint:

```bash
curl -sS -X POST https://portal.empresa.local/api/v1/lockouts/{id}/link-ticket \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "ticket_id": 4821,
        "ticket_url": "https://glpi.empresa.local/front/ticket.form.php?id=4821"
      }'
```

- `{id}` é o identificador da investigação/lockout no portal.
- O vínculo fica registrado no histórico da investigação (auditável), permitindo correlacionar o incidente do AD com o chamado do GLPI.
- Requer papel com permissão adequada (ex.: Helpdesk/Security, conforme RBAC — ver grupos `AUTH_GROUP_*`).

---

## 6. Testar a integração

```bash
# Teste de conector administrativo (se disponível na sua versão do backend)
curl -sS -X POST https://portal.empresa.local/api/v1/admin/connectors/test \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"connector_type":"glpi"}' | jq
```

Verificações em caso de falha:

| Sintoma | Causa provável | Ação |
|---|---|---|
| `ERROR_APP_TOKEN_PARAMETERS_MISSING` | App-Token ausente/errado | Revise `GLPI_APP_TOKEN` e o client de API |
| `ERROR_LOGIN_PARAMETERS_MISSING` / 401 | user_token inválido ou API desabilitada | Regenere o user_token; habilite a API REST |
| `ERROR_GLPI_LOGIN_USER_TOKEN` / IP negado | IP do worker fora do range do client de API | Ajuste os IPs permitidos no client de API |
| Ticket criado na entidade errada | `GLPI_ENTITY_ID` incorreto | Ajuste o ID da entidade |
| Muitos tickets duplicados | Janela de dedup curta | Aumente `GLPI_DEDUP_WINDOW_HOURS` |
| Nenhum ticket automático | Alerta não é CRÍTICO ou flag desligada | Confirme `GLPI_CREATE_TICKET_ON_CRITICAL=true` |
