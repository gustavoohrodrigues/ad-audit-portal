# Guia de Configuração LDAP / LDAPS

Este documento descreve como conectar o **AD Audit Portal** ao Active Directory de forma **somente leitura**, usando LDAPS (LDAP sobre TLS) com validação de certificado, o princípio do menor privilégio e uma conta de serviço dedicada.

> **Importante:** o AD Audit Portal **nunca** escreve no Active Directory. Ele não desbloqueia contas, não redefine senhas, não cria/exclui contas e não gerencia grupos. A conta de serviço abaixo deve ter **apenas leitura**.

---

## 1. Visão geral das variáveis do `.env`

| Variável | Descrição | Exemplo |
|---|---|---|
| `AD_BIND_USERNAME` | UPN ou `sAMAccountName` da conta de serviço de leitura | `svc_ad_audit@empresa.local` |
| `AD_BIND_PASSWORD` | Senha da conta de serviço (preferir Docker Secret) | `***` |
| `AD_BIND_DN` | DN completo da conta de serviço (usado no bind quando necessário) | `CN=svc_ad_audit,OU=Service Accounts,DC=empresa,DC=local` |
| `AD_LDAP_URI` | URI primária LDAPS | `ldaps://dc01.empresa.local:636` |
| `AD_LDAP_FALLBACK_URI` | URI secundária (outro DC) para tolerância a falhas | `ldaps://dc02.empresa.local:636` |
| `AD_LDAP_TLS_VERIFY` | Valida a cadeia TLS do DC (**deve ser `true` em produção**) | `true` |
| `AD_LDAP_CA_CERT_PATH` | Caminho do certificado da CA dentro do container | `/run/secrets/ad_ca_certificate.pem` |
| `AD_USERS_SEARCH_BASE` | Base de busca de usuários | `OU=Usuarios,DC=empresa,DC=local` |
| `AD_COMPUTERS_SEARCH_BASE` | Base de busca de computadores | `OU=Computadores,DC=empresa,DC=local` |
| `AD_GROUPS_SEARCH_BASE` | Base de busca de grupos | `OU=Grupos,DC=empresa,DC=local` |
| `AD_SERVICE_ACCOUNTS_SEARCH_BASE` | Base de busca de contas de serviço | `OU=Service Accounts,DC=empresa,DC=local` |

O certificado da CA é entregue via **Docker Secret**: o arquivo físico fica em `secrets/ad_ca_certificate.pem` no host e é montado no container em `/run/secrets/ad_ca_certificate.pem`.

---

## 2. Criação da conta de serviço do AD

Execute em um Domain Controller (ou estação com o módulo `ActiveDirectory` do RSAT), com uma conta que tenha permissão para criar objetos na OU de contas de serviço.

```powershell
Import-Module ActiveDirectory

# Gere uma senha forte e aleatória (>= 24 caracteres)
$pwd = ConvertTo-SecureString -AsPlainText -Force `
  (([char[]](33..126) | Get-Random -Count 32) -join '')

New-ADUser `
  -Name "svc_ad_audit" `
  -SamAccountName "svc_ad_audit" `
  -UserPrincipalName "svc_ad_audit@empresa.local" `
  -DisplayName "Service - AD Audit Portal (READ ONLY)" `
  -Description "Conta de leitura para o AD Audit Portal. NAO CONCEDER ESCRITA." `
  -Path "OU=Service Accounts,DC=empresa,DC=local" `
  -AccountPassword $pwd `
  -Enabled $true `
  -PasswordNeverExpires $true `
  -CannotChangePassword $true

# A senha nao expira (conta de serviço), mas registre a rotação manual no cofre de segredos.
Set-ADUser -Identity "svc_ad_audit" -PasswordNeverExpires $true
```

Recomendações:

- Marque **"A senha nunca expira"** (`PasswordNeverExpires`) e **"O usuário não pode alterar a senha"** para evitar interrupções, **desde que** a senha seja longa/aleatória e rotacionada por processo controlado (ver `hardening.md`).
- Considere restringir os horários/estações de logon interativo (a conta **não** deve fazer logon interativo — apenas bind LDAP).
- **Não** adicione a conta a nenhum grupo privilegiado (`Domain Admins`, `Enterprise Admins`, `Account Operators`, etc.).
- Aplique a flag "Esta conta é sensível e não pode ser delegada" (`AccountNotDelegated`) para reduzir risco de delegação Kerberos:

```powershell
Set-ADUser -Identity "svc_ad_audit" -AccountNotDelegated $true
```

---

## 3. Permissões mínimas (menor privilégio)

A conta de serviço precisa **somente de LEITURA (Read / Read Property)** sobre os objetos e atributos consultados pelo portal. Ela **NÃO** deve ter:

- direito de **escrita** em nenhum atributo;
- direito de **reset de senha** (`Reset Password` / `Change Password`);
- direito de **criar/excluir** objetos;
- associação a **grupos privilegiados**.

### 3.1 Atributos lidos pelo portal

A conta precisa de `Read Property` nestes atributos (usuários, computadores, grupos, OUs):

```
sAMAccountName, userPrincipalName, displayName, givenName, sn, mail,
employeeID, department, title, manager, distinguishedName, memberOf,
whenCreated, whenChanged, pwdLastSet, lastLogonTimestamp, lastLogon,
userAccountControl, accountExpires, badPwdCount, badPasswordTime,
lockoutTime, objectSID, objectGUID, adminCount, servicePrincipalName,
msDS-AllowedToDelegateTo, SIDHistory
```

### 3.2 Delegação via "Delegation of Control Wizard" (GUI)

1. Em **Active Directory Users and Computers**, clique com o botão direito na OU raiz de leitura (ou em cada base de busca).
2. Selecione **Delegate Control...** → **Add** → escolha `svc_ad_audit`.
3. Em **"Create a custom task to delegate"** selecione **"This folder, existing objects in this folder, and creation of new objects..."**.
4. Marque apenas **General** → **Read** (e, se aparecer, **Read All Properties**). **Não** marque Write, Create, Delete, Reset Password.
5. Repita para as OUs de Usuários, Computadores, Grupos e Service Accounts (ou aplique na raiz do domínio herdando para baixo, conforme política).

### 3.3 Delegação via `dsacls` (linha de comando)

Conceda leitura recursiva (herdada) somente de propriedades e conteúdo:

```powershell
# Read Property (RP) + List Contents (LC) + Read Control (RC) herdados para todos os objetos
dsacls "OU=Usuarios,DC=empresa,DC=local" /I:T /G "EMPRESA\svc_ad_audit:GR"

dsacls "OU=Computadores,DC=empresa,DC=local"   /I:T /G "EMPRESA\svc_ad_audit:GR"
dsacls "OU=Grupos,DC=empresa,DC=local"         /I:T /G "EMPRESA\svc_ad_audit:GR"
dsacls "OU=Service Accounts,DC=empresa,DC=local" /I:T /G "EMPRESA\svc_ad_audit:GR"
```

- `GR` = **Generic Read** (equivale a Read Property + List + Read Permissions), **sem** qualquer direito de escrita.
- `/I:T` aplica a herança à sub-árvore.
- Verifique o resultado:

```powershell
dsacls "OU=Usuarios,DC=empresa,DC=local" | Select-String "svc_ad_audit"
```

> **Nunca** use `/G ...:GW` (Generic Write), `/G ...:WP` (Write Property), `CA;Reset Password` ou `SDDL` que conceda escrita para esta conta.

### 3.4 Atributos que podem exigir permissão adicional

- **`SIDHistory`** e atributos de delegação (`msDS-AllowedToDelegateTo`, `servicePrincipalName`) podem estar sujeitos a controle de acesso mais restrito conforme a política de segurança do domínio. Se o portal reportar valores vazios para contas que sabidamente possuem SIDHistory, conceda explicitamente `Read Property` nesses atributos:

```powershell
dsacls "DC=empresa,DC=local" /I:S /G "EMPRESA\svc_ad_audit:RPWP;sIDHistory" 2>$null
# ATENÇÃO: use APENAS RP (Read Property). Nao inclua WP. Exemplo somente-leitura:
dsacls "DC=empresa,DC=local" /I:S /G "EMPRESA\svc_ad_audit:RP;sIDHistory"
```

- Em ambientes com **AdminSDHolder**, objetos de contas privilegiadas (com `adminCount=1`) têm a herança de ACL desabilitada. A leitura desses objetos pode exigir que a delegação seja aplicada também no container `CN=AdminSDHolder,CN=System,DC=empresa,DC=local` (com cautela e apenas leitura), ou aceita-se que alguns atributos protegidos não sejam lidos.

---

## 4. Exportar o certificado da CA para `secrets/ad_ca_certificate.pem`

O portal valida a cadeia TLS do DC contra a CA que emitiu o certificado do controlador de domínio (normalmente a **Enterprise CA** interna).

### 4.1 Opção A — `certutil` (em um DC ou na CA)

```powershell
# Exporta o certificado da CA raiz/emissora em formato PEM
certutil -ca.cert C:\temp\ad_ca_certificate.cer

# Converte DER -> PEM se necessário
certutil -encode C:\temp\ad_ca_certificate.cer C:\temp\ad_ca_certificate.pem
```

### 4.2 Opção B — `openssl` (capturando direto do DC)

```bash
# Captura a cadeia apresentada pelo DC na porta 636 e extrai os certificados
openssl s_client -connect dc01.empresa.local:636 -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform PEM > secrets/ad_ca_certificate.pem

# Para pegar toda a cadeia (root + issuing), extraia cada bloco BEGIN/END CERTIFICATE
# e concatene o(s) certificado(s) de CA no arquivo PEM final.
```

### 4.3 Validar o arquivo PEM

```bash
openssl x509 -in secrets/ad_ca_certificate.pem -noout -subject -issuer -dates
```

Garanta que:

- o arquivo contém a **CA emissora e/ou raiz** (não apenas o cert do DC);
- as permissões do arquivo no host são restritas (`chmod 640 secrets/ad_ca_certificate.pem`);
- o `docker-compose` monta esse arquivo como secret em `/run/secrets/ad_ca_certificate.pem` (valor de `AD_LDAP_CA_CERT_PATH`).

---

## 5. Configurar o `.env`

```dotenv
AUTH_PROVIDER=ldap
AUTH_LDAP_USER_FILTER=(&(objectClass=user)(sAMAccountName={username}))

AD_BIND_USERNAME=svc_ad_audit@empresa.local
AD_BIND_PASSWORD=__use_docker_secret__
AD_BIND_DN=CN=svc_ad_audit,OU=Service Accounts,DC=empresa,DC=local

AD_LDAP_URI=ldaps://dc01.empresa.local:636
AD_LDAP_FALLBACK_URI=ldaps://dc02.empresa.local:636
AD_LDAP_TLS_VERIFY=true
AD_LDAP_CA_CERT_PATH=/run/secrets/ad_ca_certificate.pem

AD_USERS_SEARCH_BASE=OU=Usuarios,DC=empresa,DC=local
AD_COMPUTERS_SEARCH_BASE=OU=Computadores,DC=empresa,DC=local
AD_GROUPS_SEARCH_BASE=OU=Grupos,DC=empresa,DC=local
AD_SERVICE_ACCOUNTS_SEARCH_BASE=OU=Service Accounts,DC=empresa,DC=local

# Grupos RBAC da aplicação (mapeados para papéis)
AUTH_GROUP_VIEWERS=CN=ADAudit-Viewers,OU=Grupos,DC=empresa,DC=local
AUTH_GROUP_HELPDESK=CN=ADAudit-Helpdesk,OU=Grupos,DC=empresa,DC=local
AUTH_GROUP_SECURITY=CN=ADAudit-Security,OU=Grupos,DC=empresa,DC=local
AUTH_GROUP_ADMINS=CN=ADAudit-Admins,OU=Grupos,DC=empresa,DC=local
```

> A autenticação de usuários do portal também usa LDAP: o filtro `AUTH_LDAP_USER_FILTER` localiza o usuário pelo `sAMAccountName` e o papel (RBAC) é definido pela associação aos grupos `AUTH_GROUP_*` (via atributo `memberOf`).

---

## 6. Validar a conectividade

### 6.1 Com `ldapsearch` (Linux)

```bash
LDAPTLS_CACERT=secrets/ad_ca_certificate.pem \
ldapsearch -H ldaps://dc01.empresa.local:636 \
  -D "svc_ad_audit@empresa.local" -W \
  -b "OU=Usuarios,DC=empresa,DC=local" \
  "(sAMAccountName=algum_usuario)" \
  sAMAccountName displayName userAccountControl lockoutTime
```

Teste que a validação TLS está funcionando (deve **falhar** se a CA estiver errada):

```bash
# Sem informar a CA correta, o handshake deve ser recusado quando TLS_VERIFY=true
ldapsearch -H ldaps://dc01.empresa.local:636 -x -b "DC=empresa,DC=local" -s base
```

### 6.2 Com PowerShell

```powershell
# Teste de porta LDAPS
Test-NetConnection dc01.empresa.local -Port 636

# Bind e consulta de leitura
$cred = Get-Credential  # svc_ad_audit@empresa.local
$de = New-Object System.DirectoryServices.DirectoryEntry(
  "LDAP://dc01.empresa.local:636/OU=Usuarios,DC=empresa,DC=local",
  $cred.UserName, $cred.GetNetworkCredential().Password,
  [System.DirectoryServices.AuthenticationTypes]::SecureSocketsLayer)
$searcher = New-Object System.DirectoryServices.DirectorySearcher($de)
$searcher.Filter = "(sAMAccountName=algum_usuario)"
$searcher.FindOne().Properties["displayname"]
```

### 6.3 Pelo endpoint de teste da aplicação

Após subir o backend, valide o conector LDAP pela API administrativa (requer papel de admin):

```bash
curl -sS -X POST https://portal.empresa.local/api/v1/admin/connectors/test \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"connector_type":"ldap"}' | jq
```

Resposta esperada (exemplo):

```json
{
  "connector_type": "ldap",
  "status": "ok",
  "target": "ldaps://dc01.empresa.local:636",
  "tls_verified": true,
  "bind_dn": "CN=svc_ad_audit,OU=Service Accounts,DC=empresa,DC=local",
  "search_bases_reachable": true,
  "latency_ms": 42
}
```

Se `status` for `error`, verifique nesta ordem: resolução DNS do DC, porta 636 liberada no firewall, validade/cadeia do certificado da CA, credenciais da conta de serviço e as bases de busca.

---

## 7. Solução de problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| `TLS: hostname does not match CN` | Certificado emitido para outro FQDN | Use o FQDN correto na URI; reexporte a cadeia |
| `certificate verify failed` | CA errada em `AD_LDAP_CA_CERT_PATH` | Reexporte a CA emissora (seção 4) |
| `invalid credentials (49)` | Usuário/senha incorretos ou conta bloqueada | Verifique `AD_BIND_*`; a própria conta de serviço não deve estar bloqueada |
| Atributos vazios (`SIDHistory`, delegação) | Falta `Read Property` no atributo | Conceda leitura adicional (seção 3.4) |
| Timeout intermitente | DC primário indisponível | Confirme `AD_LDAP_FALLBACK_URI` |

Consulte também `hardening.md` para rotação de segredos e uso de Docker Secrets/Vault.
