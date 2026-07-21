# Guia de GPO para Auditoria Avançada

Para que os Domain Controllers **gerem** os Event IDs coletados pelo AD Audit Portal, é preciso habilitar as subcategorias corretas da **Advanced Audit Policy** via GPO, forçar a precedência das subcategorias e, para os eventos de Directory Service (5136/5137/5141), configurar a auditoria de acesso no objeto (**SACL**).

> Aplicar a GPO à OU **Domain Controllers**. As mudanças só têm efeito após replicação + `gpupdate`.

---

## 1. Forçar precedência das subcategorias

Em domínios modernos, as subcategorias de auditoria avançada só têm efeito se a política legada de auditoria for ignorada:

**Computer Configuration → Policies → Windows Settings → Security Settings → Local Policies → Security Options →**
**"Audit: Force audit policy subcategory settings (Windows Vista or later) to override audit policy category settings"** → **Enabled**.

Sem isso, as configurações granulares de subcategoria podem ser sobrepostas pelas categorias legadas.

---

## 2. Subcategorias necessárias (Advanced Audit Policy Configuration)

Caminho na GPO:
**Computer Configuration → Policies → Windows Settings → Security Settings → Advanced Audit Policy Configuration → Audit Policies →**

Configure **Success** (e **Success and Failure** quando indicado):

### Account Logon
- **Audit Kerberos Authentication Service** → Success and Failure → gera **4771**
- **Audit Kerberos Service Ticket Operations** → Success and Failure
- **Audit Credential Validation** → Success and Failure → gera **4776**

### Account Management
- **Audit User Account Management** → Success and Failure → gera **4720, 4722, 4723, 4724, 4725, 4726, 4738, 4740, 4767, 4781**
- **Audit Security Group Management** → Success → gera **4728, 4729, 4732, 4733, 4756, 4757**
- **Audit Computer Account Management** → Success → eventos de conta de computador

### Logon/Logoff
- **Audit Logon** → Success and Failure → gera **4624, 4625**
- **Audit Account Lockout** → Success and Failure → reforça a geração/registro de **4740**

### DS Access
- **Audit Directory Service Changes** → Success → gera **5136, 5137, 5141** (requer SACL, ver seção 5)

---

## 3. Tabela: subcategoria → Event IDs gerados

| Categoria | Subcategoria | Event IDs |
|---|---|---|
| Account Logon | Audit Kerberos Authentication Service | 4771 |
| Account Logon | Audit Kerberos Service Ticket Operations | (TGS) 4769/4770 |
| Account Logon | Audit Credential Validation | 4776 |
| Account Management | Audit User Account Management | 4720, 4722, 4723, 4724, 4725, 4726, 4738, 4740, 4767, 4781 |
| Account Management | Audit Security Group Management | 4728, 4729, 4732, 4733, 4756, 4757 |
| Account Management | Audit Computer Account Management | 4741, 4742, 4743 |
| Logon/Logoff | Audit Logon | 4624, 4625 |
| Logon/Logoff | Audit Account Lockout | 4740 |
| DS Access | Audit Directory Service Changes | 5136, 5137, 5141 |

> Os Event IDs efetivamente **coletados** pelo portal são os listados em `wef.md`. Esta tabela mostra a origem de auditoria de cada um.

---

## 4. Verificar e ajustar com `auditpol`

Consultar a política efetiva em um DC:

```powershell
# Estado de todas as subcategorias
auditpol /get /category:*

# Subcategorias específicas
auditpol /get /subcategory:"User Account Management"
auditpol /get /subcategory:"Security Group Management"
auditpol /get /subcategory:"Logon"
auditpol /get /subcategory:"Credential Validation"
auditpol /get /subcategory:"Kerberos Authentication Service"
auditpol /get /subcategory:"Directory Service Changes"
auditpol /get /subcategory:"Account Lockout"
```

Saída esperada (exemplo): `User Account Management   Success and Failure`.

Definir manualmente (para teste/laboratório — em produção prefira **GPO**, que é reaplicada):

```powershell
auditpol /set /subcategory:"User Account Management" /success:enable /failure:enable
auditpol /set /subcategory:"Security Group Management" /success:enable
auditpol /set /subcategory:"Logon" /success:enable /failure:enable
auditpol /set /subcategory:"Account Lockout" /success:enable /failure:enable
auditpol /set /subcategory:"Credential Validation" /success:enable /failure:enable
auditpol /set /subcategory:"Kerberos Authentication Service" /success:enable /failure:enable
auditpol /set /subcategory:"Directory Service Changes" /success:enable
```

> `auditpol /set` altera a política **efetiva local**; a próxima aplicação de GPO pode sobrescrevê-la. Use `auditpol` para diagnóstico e a GPO como fonte da verdade.

Backup/restauração da configuração:

```powershell
auditpol /backup /file:C:\audit\auditpol-baseline.csv
auditpol /restore /file:C:\audit\auditpol-baseline.csv
```

---

## 5. SACL para Directory Service Changes (5136/5137/5141)

Habilitar a subcategoria **Audit Directory Service Changes** **não basta**: o Windows só emite 5136/5137/5141 para objetos/atributos cuja **SACL** (System Access Control List) audita a operação de escrita. Configure a auditoria no nível do objeto/OU que deseja monitorar.

### 5.1 Via GUI (ADSI Edit ou ADUC com Advanced Features)

1. Abra **ADSI Edit** (ou ADUC com **View → Advanced Features**).
2. Botão direito na partição/OU (ex.: `DC=empresa,DC=local` ou a OU de contas privilegiadas) → **Properties → Security → Advanced → Auditing → Add**.
3. **Principal:** `Everyone` (ou `Authenticated Users`).
4. **Type:** `Success`.
5. **Applies to:** `This object and all descendant objects`.
6. **Permissions:** marque **Write all properties** (e, conforme a política, Create/Delete de objetos filhos).
7. Aplique.

Com a SACL de escrita, cada alteração de atributo em objeto do diretório passa a gerar **5136** (valor de atributo modificado), **5137** (objeto criado) e **5141** (objeto excluído).

### 5.2 Via `dsacls` (auditoria — flag /S)

```powershell
# Exemplo: auditar sucesso de escrita de propriedades em uma OU sensível (herdado)
dsacls "OU=Service Accounts,DC=empresa,DC=local" /I:T /S:S "Everyone:WP"
```

> Ajuste o escopo com cuidado: auditar escrita em todo o domínio gera volume alto de 5136. Priorize OUs de contas privilegiadas, contas de serviço, grupos administrativos e objetos críticos (`CRITICAL_OUS`, `PRIVILEGED_GROUPS`).

---

## 6. Tamanho do log e retenção no DC

Garanta que o log **Security** dos DCs seja grande o suficiente para não perder eventos entre exportações WEF:

**Computer Configuration → Policies → Windows Settings → Security Settings → Event Log →** ou via GPO Administrative Templates. Recomendado: **Maximum Security log size ≥ 1–4 GB** e retenção "Overwrite events as needed". Como os eventos são encaminhados (WEF) e persistidos no portal, o log local funciona apenas como buffer.

```powershell
# Consultar/ajustar tamanho do log Security (exemplo: 4 GB)
wevtutil gl Security
wevtutil sl Security /ms:4294967296
```

---

## 7. Aplicar e validar

```powershell
# Nos DCs
gpupdate /force

# Confirmar que as subcategorias estao ativas
auditpol /get /category:"Account Management","Logon/Logoff","Account Logon","DS Access"

# Gerar um evento de teste controlado e conferir no log
# (ex.: uma troca de grupo em laboratorio deve produzir 4728/4732)
Get-WinEvent -LogName Security -MaxEvents 20 |
  Where-Object Id -in 4624,4625,4740,4728,5136 |
  Select-Object TimeCreated, Id, @{n='Msg';e={$_.Message.Split("`n")[0]}}
```

Depois de gerar tráfego de auditoria, confirme a chegada no portal via `wef.md` (seção Monitoramento) e no dashboard de Domain Controllers. Se um Event ID esperado não aparece:

1. confirme a subcategoria correspondente com `auditpol /get`;
2. verifique se **"Force audit policy subcategory settings"** está `Enabled`;
3. para 5136/5137/5141, confirme a **SACL** no objeto/OU;
4. confirme o encaminhamento WEF (subscription ativa e filtro do Event ID).
