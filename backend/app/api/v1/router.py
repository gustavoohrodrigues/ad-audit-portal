"""Agrega todos os routers da API v1."""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    alerts,
    auth,
    broadcast,
    capacity,
    chat_webhooks,
    computers,
    dashboard,
    detections,
    events,
    groups,
    health,
    inventory,
    lockouts,
    maintenance,
    monitoring,
    notifications,
    reports,
    search,
    users,
    watchlists,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(users.router)
api_router.include_router(search.router)
api_router.include_router(notifications.router)
api_router.include_router(chat_webhooks.router)
api_router.include_router(broadcast.router)
api_router.include_router(detections.router)
api_router.include_router(watchlists.router)
api_router.include_router(inventory.router)
api_router.include_router(groups.router)
api_router.include_router(computers.router)
api_router.include_router(events.router)
api_router.include_router(lockouts.router)
api_router.include_router(alerts.router)
api_router.include_router(monitoring.router)
api_router.include_router(reports.router)
api_router.include_router(admin.router)
api_router.include_router(capacity.router)
api_router.include_router(maintenance.router)
