"""Fixtures e configuração de ambiente para os testes do backend."""
import os
import sys
from pathlib import Path

# garante variáveis mínimas antes de importar app.config
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-1234567890abcdef")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-key-abcdef1234567890abcd")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("AD_ENABLED", "false")
os.environ.setdefault("AUTH_PROVIDER", "ldap")

# adiciona backend/ ao path
BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))
