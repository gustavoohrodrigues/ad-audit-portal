.PHONY: help setup build up down logs ps restart migrate seed backup restore health test lint fmt

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:   ## Gera .env com segredos e placeholders
	./scripts/setup.sh

build:   ## Build de todas as imagens
	docker compose build

up:      ## Sobe a stack (migrations automáticas)
	docker compose up -d

prod:    ## Sobe a stack com override de produção
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

down:    ## Derruba a stack
	docker compose down

logs:    ## Logs de todos os serviços
	docker compose logs -f

ps:      ## Status dos containers
	docker compose ps

restart: ## Reinicia a stack
	docker compose restart

migrate: ## Aplica migrations manualmente
	docker compose run --rm backend alembic upgrade head

seed:    ## Insere dados de demonstração (NÃO usar em produção)
	./scripts/seed_demo.sh

backup:  ## Backup lógico do PostgreSQL
	./scripts/backup.sh

restore: ## Restaura backup: make restore FILE=backups/arquivo.dump
	./scripts/restore.sh $(FILE)

health:  ## Verifica saúde da stack
	./scripts/healthcheck.sh

test:    ## Roda os testes (requer deps instaladas)
	pytest -q

lint:    ## Lint do backend/collector/worker
	ruff check backend collector worker
