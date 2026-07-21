"""Watchlists de entidades monitoradas (contas/grupos/computadores críticos)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.models.analytics import Watchlist, WatchlistItem
from app.schemas import WatchlistCreate, WatchlistItemCreate

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


@router.get("")
async def list_watchlists(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> dict:
    lists = (await session.execute(select(Watchlist).order_by(Watchlist.created_at))).scalars().all()
    out = []
    for wl in lists:
        items = (
            await session.execute(select(WatchlistItem).where(WatchlistItem.watchlist_id == wl.id))
        ).scalars().all()
        out.append({
            "id": wl.id, "name": wl.name, "description": wl.description, "owner": wl.owner,
            "items": [
                {"id": i.id, "entity_type": i.entity_type, "entity_ref": i.entity_ref, "note": i.note}
                for i in items
            ],
        })
    return {"watchlists": out}


@router.post("")
async def create_watchlist(
    payload: WatchlistCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("note:write")),
) -> dict:
    wl = Watchlist(name=payload.name, description=payload.description, owner=user.username)
    session.add(wl)
    await session.commit()
    await session.refresh(wl)
    return {"id": wl.id, "name": wl.name}


@router.post("/{watchlist_id}/items")
async def add_item(
    watchlist_id: int,
    payload: WatchlistItemCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("note:write")),
) -> dict:
    wl = await session.get(Watchlist, watchlist_id)
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist não encontrada")
    item = WatchlistItem(
        watchlist_id=watchlist_id,
        entity_type=payload.entity_type,
        entity_ref=payload.entity_ref,
        note=payload.note,
        added_by=user.username,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return {"id": item.id}


@router.delete("/{watchlist_id}/items/{item_id}")
async def remove_item(
    watchlist_id: int,
    item_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("note:write")),
) -> dict:
    item = await session.get(WatchlistItem, item_id)
    if not item or item.watchlist_id != watchlist_id:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    await session.delete(item)
    await session.commit()
    return {"deleted": item_id}
