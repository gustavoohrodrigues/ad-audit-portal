# secrets/

Coloque aqui os arquivos sensíveis usados como **Docker Secrets**. Nenhum
arquivo real deste diretório é versionado (ver `.gitignore`).

Arquivos esperados:

| Arquivo | Descrição |
|---|---|
| `ad_ca_certificate.pem` | Certificado da CA que assina o LDAPS dos Domain Controllers. Usado para validar o certificado nas conexões LDAPS (`AD_LDAP_TLS_VERIFY=true`). |
| `tls_certificate.pem` *(opcional)* | Certificado TLS, caso você faça terminação TLS interna (normalmente feita no NPM). |
| `tls_private_key.pem` *(opcional)* | Chave privada correspondente. |

## Como obter o `ad_ca_certificate.pem`

No controlador de domínio / CA da empresa, exporte a CA raiz em formato Base-64 (PEM):

```powershell
certutil -ca.cert C:\temp\ad_ca.cer
# converta para PEM se necessário:
openssl x509 -inform DER -in ad_ca.cer -out ad_ca_certificate.pem
```

Copie o `.pem` para este diretório com o nome `ad_ca_certificate.pem`.

> Se você ainda não tem o certificado e quer subir a stack para avaliação,
> o script `scripts/setup.sh` cria um placeholder vazio. Nesse caso, defina
> `AD_LDAP_TLS_VERIFY=false` **apenas em ambiente de laboratório** — nunca em produção.
