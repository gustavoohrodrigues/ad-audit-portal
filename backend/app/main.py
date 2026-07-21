"""Entrypoint da API FastAPI do AD-Audit-Portal.

Somente leitura em relação ao AD: nenhum endpoint altera objetos, atributos
ou permissões do Active Directory. Não há desbloqueio, reset de senha ou
gestão de contas/grupos.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# validate_required_settings roda aqui: se faltar variável obrigatória, o
# processo falha no import com mensagem clara (ver config.py).
from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import (
    MetricsMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)

settings = get_settings()
configure_logging(settings.log_level, settings.log_format)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    from app.services.scheduler import ad_sync_loop, posture_snapshot_loop

    logger.info(
        "Iniciando %s (env=%s, provider=%s)",
        settings.app_name,
        settings.app_env,
        settings.auth_provider,
    )
    sync_task = asyncio.create_task(ad_sync_loop())
    snapshot_task = asyncio.create_task(posture_snapshot_loop())
    yield
    sync_task.cancel()
    snapshot_task.cancel()
    logger.info("Encerrando %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description=(
        "Central de auditoria de identidades do Active Directory. "
        "**Somente leitura** — nenhuma ação altera o AD."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS restrito às origens configuradas.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):  # noqa: ANN001
    logger.exception("Erro não tratado em %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Erro interno"})


# Router principal — importado após settings validados.
from app.api.v1.router import api_router  # noqa: E402

app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"app": settings.app_name, "docs": "/api/docs"}
