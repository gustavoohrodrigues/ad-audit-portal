# Detecções Defensivas (Superfície de Ataque)

O módulo **Superfície de Ataque** (`/attack-surface`) e o **Score de Segurança**
avaliam a exposição do AD a partir dos objetos sincronizados (LDAP, somente
leitura). **Nada é explorado** — apenas classificamos exposição, com evidências,
risco e recomendação. Referências MITRE ATT&CK incluídas por transparência.

## Detecções implementadas

| Detecção | Endpoint | MITRE | O que identifica |
|---|---|---|---|
| **Kerberoasting** | `GET /api/v1/detections/kerberoasting` | T1558.003 | Contas de **usuário com SPN** (alvo de crack de ticket de serviço) |
| **AS-REP Roasting** | `GET /api/v1/detections/asrep-roasting` | T1558.004 | Contas com **DONT_REQ_PREAUTH** (pré-autenticação Kerberos desabilitada) |
| **Stale Admins** | `GET /api/v1/detections/stale-admins` | — | Contas **privilegiadas** inativas, com senha antiga, expiradas-ativas, nunca-expira ou password-not-required |
| Resumo | `GET /api/v1/detections/summary` | — | Contagem consolidada |

RBAC: as listas detalhadas exigem `critical:read` (security_analyst /
administrator). O resumo exige `dashboard:read`.

## Pontuação de risco

Cada conta recebe um score 0–100 combinando o base da técnica com fatores de
agravamento: privilégio (+25), `adminCount` (+15), senha nunca expira (+10),
senha não trocada há +1 ano (+15). Ordenação por risco decrescente.

## Como remediar

- **Kerberoasting**: use **gMSA** ou senhas longas (25+ caracteres) para contas
  de serviço; evite SPN em contas de usuário privilegiadas.
- **AS-REP Roasting**: reative a pré-autenticação Kerberos (remova a flag
  `DONT_REQ_PREAUTH` do `userAccountControl`). *(Ação feita no AD pelo
  administrador — o portal apenas aponta; nunca altera o AD.)*
- **Stale Admins**: revise, rotacione ou desabilite contas administrativas
  ociosas ou mal configuradas.

## Como o dado chega

- A flag AS-REP (`dont_require_preauth`) é derivada do `userAccountControl`
  (`0x400000`) em `backend/app/ldap/converters.py` e persistida em
  `ad_users.dont_require_preauth` durante o sync.
- SPN vem de `servicePrincipalName`; delegação de `msDS-AllowedToDelegateTo`;
  SIDHistory de `sIDHistory`.

## Roadmap (próximas detecções)
- **Password spray** (correlação de 4625/4771/4776) — depende da coleta WEF real.
- **Anomalias Kerberos** (4768/4769/4770/4773 fora de baseline) — depende do WEF.
- **Mini-BloodHound**: caminhos por aninhamento de grupos até Domain Admins.
