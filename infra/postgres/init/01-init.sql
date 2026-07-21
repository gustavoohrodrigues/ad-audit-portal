-- Inicialização do PostgreSQL para o AD-Audit-Portal.
-- Executado apenas na primeira criação do volume de dados.

-- Extensões úteis para busca e análise.
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- busca por similaridade (ILIKE rápido)
CREATE EXTENSION IF NOT EXISTS btree_gin;    -- índices GIN em colunas comuns

-- Fuso padrão de exibição (a aplicação converte explicitamente, mas ajuda em queries ad-hoc).
ALTER DATABASE ad_audit SET timezone TO 'America/Sao_Paulo';
