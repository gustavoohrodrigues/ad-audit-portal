"""Camada de acesso a dados — SQLModel/SQLAlchemy assíncrono (asyncpg/psycopg)."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.config import get_settings

settings = get_settings()

# DATABASE_URL usa driver psycopg (v3). Para async trocamos para +asyncpg? Não —
# psycopg v3 tem suporte async nativo via create_async_engine com o mesmo dialeto.
_async_url = settings.database_url
if _async_url.startswith("postgresql+psycopg://"):
    # psycopg3 já é compatível com asyncio no SQLAlchemy 2.x
    pass

# Hardening: statement_timeout evita queries descontroladas segurarem conexões.
_connect_args: dict = {}
if _async_url.startswith("postgresql+psycopg://") and settings.db_statement_timeout_ms > 0:
    _connect_args["options"] = f"-c statement_timeout={settings.db_statement_timeout_ms}"

engine = create_async_engine(
    _async_url,
    echo=settings.app_debug,
    pool_pre_ping=True,
    pool_size=settings.api_sql_pool_size,
    max_overflow=settings.api_sql_max_overflow,
    pool_recycle=settings.api_sql_pool_recycle_seconds,
    connect_args=_connect_args,
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependência FastAPI: fornece uma sessão de banco por request."""
    async with SessionLocal() as session:
        yield session


async def init_models() -> None:
    """Cria as tabelas caso não existam (uso em dev/testes; produção usa Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
