# Subir no Git e clonar no servidor — passo a passo

Serve para GitHub, GitLab ou Gitea (self-hosted). O repositório local já está
inicializado com o 1º commit e o `.gitignore` protege `.env`, `secrets/`, chaves
e certificados.

## Parte A — O que CADASTRAR na plataforma Git

1. **Criar um repositório VAZIO** (sem README/.gitignore, para não conflitar):
   - GitHub: New repository → *Private* → **não** marque "Add README".
   - GitLab: New project → Create blank project → *Private*.
   - Gitea: New Migration/Repository → deixe vazio.
   - Anote a URL, ex.: `git@git.astra-sa.com:infra/ad-audit-portal.git` (SSH)
     ou `https://git.astra-sa.com/infra/ad-audit-portal.git` (HTTPS).

2. **Cadastrar a autenticação** (escolha UMA):
   - **Chave SSH** (recomendado):
     ```bash
     ssh-keygen -t ed25519 -C "ad-audit-deploy" -f ~/.ssh/ad_audit_deploy
     cat ~/.ssh/ad_audit_deploy.pub    # cole no Git: Settings → SSH Keys
     ```
     Para o servidor de produção, cadastre a chave pública dele como
     **Deploy Key** (read-only) no repositório.
   - **Token (HTTPS)**: gere um *Personal Access Token* (escopo repo/read_write)
     e use no lugar da senha ao dar `git push`/`clone`.

## Parte B — Enviar o projeto (da sua máquina atual)

```bash
cd ~/ad-audit-portal

# adicione o remote (troque pela URL do seu repo)
git remote add origin git@git.astra-sa.com:infra/ad-audit-portal.git

# envie a branch main
git push -u origin main
```
Se usar HTTPS, o Git pedirá usuário + token no primeiro push.

> Confirme que **NÃO** subiu segredo: no Git, verifique que existe apenas
> `.env.example` (e não `.env`) e que `secrets/` só tem `README.md`/`.gitkeep`.

## Parte C — Preparar o SERVIDOR de aplicação

### C1. Pré-requisitos (uma vez)
```bash
# Docker Engine + Compose plugin (Debian/Ubuntu)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # relogue depois
docker compose version
git --version
```

### C2. Estrutura de pastas

| Caminho | O quê | Onde fica |
|---|---|---|
| `/opt/ad-audit-portal` | **código** (git clone) | disco local do servidor |
| `/mnt/gv0/ad-audit/pgdata` | dados do PostgreSQL | Ceph |
| `/mnt/gv0/ad-audit/redisdata` | dados do Redis | Ceph |
| `/mnt/gv0/ad-audit/wef-spool` | eventos WEF a processar | Ceph |
| `/mnt/gv0/ad-audit/backups` | dumps do pg_dump | Ceph |
| `/mnt/gv0/ad-audit/secrets` | certificado da CA do AD | Ceph |

Crie o código e o storage:
```bash
sudo mkdir -p /opt && cd /opt
git clone git@git.astra-sa.com:infra/ad-audit-portal.git
cd ad-audit-portal

# cria as pastas de dados no Ceph com as permissões corretas
sudo ./scripts/prepare-ceph-storage.sh
```

### C3. Configurar ambiente e segredos (no servidor)
```bash
./scripts/setup.sh                 # gera .env com chaves/senhas fortes
$EDITOR .env                       # AD/LDAP, SMTP, domínio, e:
                                   #   BACKUP_PATH=/mnt/gv0/ad-audit/backups
                                   #   COOKIE_SECURE=true (produção HTTPS)

# certificado da CA do AD (LDAPS), se usar:
cp <sua-ca>.pem /mnt/gv0/ad-audit/secrets/ad_ca_certificate.pem
ln -sf /mnt/gv0/ad-audit/secrets/ad_ca_certificate.pem ./secrets/ad_ca_certificate.pem
```

### C4. Subir a stack (com storage no Ceph)
```bash
export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml:docker-compose.ceph.yml
docker compose build
docker compose up -d
./scripts/healthcheck.sh
```

### C5. Publicar no NGINX Proxy Manager
Aponte o NPM para `IP-do-servidor:8088`, com SSL. Ver [`npm.md`](npm.md) e
[`deploy-server.md`](deploy-server.md).

## Atualizações futuras (redeploy)
```bash
cd /opt/ad-audit-portal
./scripts/backup.sh
git pull
docker compose build     # COMPOSE_FILE já com os 3 arquivos
docker compose up -d
```

> Regra de ouro: **sempre `build` de todas as imagens antes do `up`** — o serviço
> `migrate` tem imagem própria; rebuild parcial dessincroniza o Alembic.

## Dica: acesso do servidor ao Git sem senha
No servidor, gere/instale a chave e teste:
```bash
ssh-keygen -t ed25519 -C "servidor-ad-audit"
cat ~/.ssh/id_ed25519.pub     # cadastre como Deploy Key no repositório
ssh -T git@git.astra-sa.com   # deve autenticar
```
