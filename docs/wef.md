# Guia de Windows Event Forwarding (WEF)

O **WEF é o mecanismo primário de coleta de eventos** do AD Audit Portal. Os Domain Controllers encaminham eventos do log **Security** para um **Windows Event Collector (WEC)**, e uma tarefa de exportação transforma os eventos do log `ForwardedEvents` em **NDJSON** (um objeto JSON por linha) dentro de um **diretório spool** que o collector do portal consome.

```
[DCs] --(WinRM 5985, Source Initiated)--> [WEC / ForwardedEvents]
        --(export NDJSON)--> [WEF_SPOOL_DIR] --> [collector do AD Audit Portal] --> banco
```

> A coleta é **somente leitura**: o portal apenas lê e correlaciona eventos, nunca altera o AD.

---

## 1. Variáveis do `.env` relacionadas ao WEF

| Variável | Descrição | Padrão |
|---|---|---|
| `EVENT_COLLECTOR_MODE` | Modo de coleta: `wef` \| `winrm` \| `elastic` \| `wazuh` \| `graylog` \| `splunk` \| `api` | `wef` |
| `WEF_ENABLED` | Habilita o conector WEF | `true` |
| `WEF_HOST` | Host/coletor WEC (informativo/monitoramento) | `wef-collector` |
| `WEF_PORT` | Porta WinRM do WEC | `5985` |
| `WEF_LOG_NAME` | Nome do log encaminhado | `ForwardedEvents` |
| `WEF_SPOOL_DIR` | Diretório spool com os NDJSON | `/data/wef-spool` |

No `docker-compose`, `WEF_SPOOL_DIR` é o ponto de montagem do volume **`wefspool`**, compartilhado entre o processo que grava o NDJSON (exportador) e o collector do portal.

### Conector alternativo WinRM (pull direto dos DCs)

| Variável | Descrição | Padrão |
|---|---|---|
| `WINRM_ENABLED` | Habilita coleta via WinRM (pull) | `false` |
| `WINRM_USERNAME` | Conta de leitura de eventos | `svc_ad_event_reader` |
| `WINRM_TRANSPORT` | Transporte WinRM | `ntlm` |
| `WINRM_USE_SSL` | Usa HTTPS (5986) | `true` |
| `WINRM_PORT` | Porta WinRM (SSL) | `5986` |
| `WINRM_DOMAIN_CONTROLLERS` | Lista de DCs (CSV) | `dc01.empresa.local,dc02.empresa.local` |

---

## 2. Event IDs coletados

O portal coleta e classifica os seguintes eventos do log Security (encaminhados via WEF):

| Event ID | Significado |
|---|---|
| 4624 | Logon com sucesso |
| 4625 | Falha de logon |
| 4720 | Criação de conta |
| 4722 | Habilitação de conta |
| 4723 | Troca de senha (pelo próprio usuário) |
| 4724 | Reset de senha (por operador) |
| 4725 | Desabilitação de conta |
| 4726 | Exclusão de conta |
| 4728 / 4732 / 4756 | Adição de membro a grupo (global / local de domínio / universal) |
| 4729 / 4733 / 4757 | Remoção de membro de grupo |
| 4738 | Alteração de conta |
| **4740** | **Bloqueio de conta (tratamento especial)** |
| 4767 | Desbloqueio de conta |
| 4771 | Falha de pré-autenticação Kerberos |
| 4776 | Validação de credencial NTLM |
| 4781 | Renomeação de conta |
| 5136 / 5137 / 5141 | Directory Service changes (alteração / criação / exclusão de objeto de diretório) |

> Consulte `gpo-audit.md` para saber **qual subcategoria de auditoria avançada** precisa estar habilitada para cada Event ID acima.

O evento **4740** recebe tratamento especial: além dos campos padrão, o portal extrai e correlaciona:
- usuário bloqueado e seu **SID**;
- horário do bloqueio e **DC** que registrou;
- **CallerComputerName** (estação/origem que causou o bloqueio);
- conta de origem;
- falhas de logon correlacionadas (4625/4771/4776);
- IP de origem;
- número de bloqueios recentes da mesma conta.

---

## 3. Configurar o Windows Event Collector (WEC)

No servidor coletor (Windows Server):

```powershell
# Habilita o serviço WinRM (necessário para WEF)
winrm quickconfig -q

# Habilita e inicia o Windows Event Collector (Wecsvc)
wecutil qc /q

# Confirma serviços
Get-Service Wecsvc, WinRM | Format-Table Name, Status, StartType
```

Garanta que o serviço **Windows Event Collector (Wecsvc)** esteja em **Automatic** e **Running**.

---

## 4. Criar a subscription (Source Computer Initiated)

Para topologias com muitos DCs, o modelo recomendado é **Source Computer Initiated** (os DCs iniciam a conexão com o coletor, configurados por GPO).

Crie um arquivo `subscription-dc-security.xml`:

```xml
<Subscription xmlns="http://schemas.microsoft.com/2006/03/windows/events/subscription">
  <SubscriptionId>DC-Security-ADAudit</SubscriptionId>
  <SubscriptionType>SourceInitiated</SubscriptionType>
  <Description>Encaminha eventos de seguranca dos DCs para o AD Audit Portal</Description>
  <Enabled>true</Enabled>
  <Uri>http://schemas.microsoft.com/wbem/wsman/1/windows/EventLog</Uri>
  <ConfigurationMode>Custom</ConfigurationMode>
  <Delivery Mode="Push">
    <Batching>
      <MaxItems>50</MaxItems>
      <MaxLatencyTime>30000</MaxLatencyTime>
    </Batching>
    <PushSettings>
      <Heartbeat Interval="60000"/>
    </PushSettings>
  </Delivery>
  <Query>
    <![CDATA[
      <QueryList>
        <Query Id="0" Path="Security">
          <Select Path="Security">
            *[System[(EventID=4624 or EventID=4625 or EventID=4720 or
                      EventID=4722 or EventID=4723 or EventID=4724 or
                      EventID=4725 or EventID=4726 or EventID=4728 or
                      EventID=4729 or EventID=4732 or EventID=4733 or
                      EventID=4738 or EventID=4740 or EventID=4756 or
                      EventID=4757 or EventID=4767 or EventID=4771 or
                      EventID=4776 or EventID=4781 or EventID=5136 or
                      EventID=5137 or EventID=5141)]]
          </Select>
        </Query>
      </QueryList>
    ]]>
  </Query>
  <ReadExistingEvents>false</ReadExistingEvents>
  <TransportName>HTTP</TransportName>
  <ContentFormat>RenderedText</ContentFormat>
  <Locale Language="pt-BR"/>
  <LogFile>ForwardedEvents</LogFile>
  <AllowedSourceNonDomainComputers></AllowedSourceNonDomainComputers>
  <AllowedSourceDomainComputers>
    O:NSG:NSD:(A;;GA;;;DC)(A;;GA;;;DD)
  </AllowedSourceDomainComputers>
</Subscription>
```

> `AllowedSourceDomainComputers` acima libera **Domain Controllers (DC)** e **Domain Computers (DD)** como origem. Ajuste o SDDL para restringir apenas aos DCs se desejar (crie um grupo e referencie seu SID).

Importe a subscription:

```powershell
wecutil cs subscription-dc-security.xml
wecutil gs DC-Security-ADAudit          # mostra a configuração
wecutil gr DC-Security-ADAudit          # mostra o runtime status por origem
```

---

## 5. GPO nos Domain Controllers (apontar para o coletor)

Crie/edite uma GPO aplicada à OU **Domain Controllers**:

**Computer Configuration → Policies → Administrative Templates → Windows Components → Event Forwarding → "Configure target Subscription Manager"** → **Enabled** → **Show...** e adicione:

```
Server=http://wef-collector:5985/wsman/SubscriptionManager/WEC
```

Para WinRM sobre HTTPS (recomendado em produção), use:

```
Server=https://wef-collector:5986/wsman/SubscriptionManager/WEC,Refresh=60
```

Force a aplicação nos DCs:

```powershell
gpupdate /force
# Reinicie o serviço WinRM para refazer a inscrição imediatamente
Restart-Service WinRM
```

### 5.1 Permissões — grupo "Event Log Readers"

O canal Security exige que a identidade que lê os eventos pertença ao grupo local **Event Log Readers** de cada DC. Para WEF (Source Initiated), a conta de máquina do DC lê o próprio Security; ainda assim, garanta que **Network Service** possa ler o log Security nos DCs:

```powershell
# Em cada DC: adiciona NETWORK SERVICE ao grupo Event Log Readers
Add-LocalGroupMember -Group "Event Log Readers" -Member "NETWORK SERVICE"
```

Se usar o conector **WinRM (pull)** com a conta `svc_ad_event_reader`, adicione essa conta ao grupo `Event Log Readers` (via GPO Restricted Groups ou localmente) em todos os DCs:

```powershell
Add-LocalGroupMember -Group "Event Log Readers" -Member "EMPRESA\svc_ad_event_reader"
```

`svc_ad_event_reader` deve ter **somente leitura** de eventos — sem direitos administrativos.

---

## 6. Exportar `ForwardedEvents` como NDJSON para o spool

O collector do portal consome **NDJSON** (uma linha JSON por evento) do diretório `WEF_SPOOL_DIR`. Há duas abordagens comuns no coletor Windows:

### 6.1 Tarefa agendada + PowerShell (simples)

Script `Export-ForwardedEvents.ps1` que lê incrementos do `ForwardedEvents` e anexa NDJSON:

```powershell
$Bookmark = "C:\wef-export\bookmark.txt"
$OutDir   = "\\wef-collector\wefspool"   # montado no volume 'wefspool' / /data/wef-spool
$Last = if (Test-Path $Bookmark) { Get-Content $Bookmark } else { (Get-Date).AddMinutes(-5).ToString("o") }

$events = Get-WinEvent -FilterHashtable @{
  LogName   = 'ForwardedEvents'
  StartTime = [datetime]$Last
} -ErrorAction SilentlyContinue

$outFile = Join-Path $OutDir ("events-{0:yyyyMMdd-HHmmss}.ndjson" -f (Get-Date))
foreach ($e in $events) {
  $obj = [ordered]@{
    time_created = $e.TimeCreated.ToString("o")
    event_id     = $e.Id
    computer     = $e.MachineName
    provider     = $e.ProviderName
    record_id    = $e.RecordId
    message      = $e.Message
    xml          = $e.ToXml()
  }
  ($obj | ConvertTo-Json -Compress) | Add-Content -Path $outFile -Encoding utf8
}

if ($events) { $events[0].TimeCreated.ToString("o") | Set-Content $Bookmark }
```

Agende a cada 1 minuto:

```powershell
$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\wef-export\Export-ForwardedEvents.ps1"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "ADAudit-ExportForwardedEvents" `
  -Action $action -Trigger $trigger -User "SYSTEM" -RunLevel Highest
```

### 6.2 NXLog (robusto, streaming)

Exemplo de `nxlog.conf` lendo `ForwardedEvents` e gravando NDJSON no spool:

```apache
<Extension json>
    Module      xm_json
</Extension>

<Input forwarded>
    Module      im_msvistalog
    Query       <QueryList>\
                  <Query Id="0"><Select Path="ForwardedEvents">*</Select></Query>\
                </QueryList>
</Input>

<Output spool>
    Module      om_file
    File        'C:\wefspool\events-' + strftime(now(), '%Y%m%d-%H') + '.ndjson'
    Exec        to_json();
</Output>

<Route wef>
    Path        forwarded => spool
</Route>
```

O diretório `C:\wefspool` (ou compartilhamento) deve corresponder ao volume `wefspool` montado em `/data/wef-spool` no container do collector. Arquivos `.ndjson` são consumidos e podem ser removidos/rotacionados após ingestão.

---

## 7. Monitoramento da coleta

O portal mantém a tabela **`domain_controllers`** com o estado de saúde de cada DC, exposta em:

```bash
curl -sS https://portal.empresa.local/api/v1/dashboard/domain-controllers \
  -H "Authorization: Bearer $TOKEN" | jq
```

Exemplo de resposta:

```json
[
  {
    "name": "dc01.empresa.local",
    "status": "healthy",
    "last_event_at": "2026-07-20T14:12:03Z",
    "last_heartbeat_at": "2026-07-20T14:12:30Z",
    "ingestion_lag_seconds": 27,
    "events_last_hour": 1842
  },
  {
    "name": "dc02.empresa.local",
    "status": "degraded",
    "last_event_at": "2026-07-20T14:03:10Z",
    "ingestion_lag_seconds": 560
  }
]
```

Critérios de status (referência):

| Status | Condição típica |
|---|---|
| `healthy` | Heartbeat recente e `ingestion_lag_seconds` baixo |
| `degraded` | Atraso de ingestão acima do limite ou heartbeat atrasado |
| `down` | Sem eventos/heartbeat além do limite (DC ou encaminhamento parado) |

Sinais que o portal acompanha por DC:
- **Heartbeat** (a subscription WEF emite heartbeats configuráveis — `Heartbeat Interval`);
- **Último evento recebido** (`last_event_at`);
- **Atraso de ingestão** (`ingestion_lag_seconds`), também exposto como métrica Prometheus `adaudit_ingestion_lag_seconds` (ver `zabbix-prometheus.md`).

Verificações rápidas no coletor Windows:

```powershell
wecutil gr DC-Security-ADAudit           # status por DC de origem (Active/Inactive)
(Get-WinEvent -LogName ForwardedEvents -MaxEvents 1).TimeCreated   # último evento
```

---

## 8. Conectores alternativos — quando usar

| Modo (`EVENT_COLLECTOR_MODE`) | Quando usar |
|---|---|
| `wef` (primário) | Padrão. Encaminhamento nativo Windows, sem agente nos DCs |
| `winrm` | Pull direto dos DCs via WinRM quando não há coletor WEF; requer `svc_ad_event_reader` e portas 5985/5986 |
| `elastic` | Já existe pipeline Winlogbeat/Elastic Agent → Elasticsearch; o portal consome dele |
| `wazuh` | SIEM Wazuh já centraliza os eventos de segurança dos DCs |
| `graylog` | Logs já enviados a um Graylog (GELF/Beats) |
| `splunk` | Ambiente com Splunk como SIEM corporativo |
| `api` | Ingestão customizada via push HTTP para a API do portal |

Escolha um único modo primário em `EVENT_COLLECTOR_MODE`. Independentemente do modo, os mesmos Event IDs (seção 2) e o tratamento especial do 4740 se aplicam.

Consulte `gpo-audit.md` (habilitar a auditoria que gera os eventos) e `zabbix-prometheus.md` (alertas de atraso/queda de fonte).
