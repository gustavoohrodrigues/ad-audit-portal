"""Relatórios: galeria, prévia e exportação (CSV/JSON). RBAC por relatório.
Exportações são auditadas. Somente leitura."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.core.rbac import has_capability
from app.database import get_session
from app.services import reports as rp
from app.services.audit import record_audit

router = APIRouter(prefix="/reports", tags=["reports"])


def _to_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _require_report(key: str, user: CurrentUser) -> rp.ReportDef:
    rd = rp.REPORTS.get(key)
    if not rd:
        raise HTTPException(status_code=404, detail="Relatório desconhecido")
    if not has_capability(user.roles, rd.capability):
        raise HTTPException(status_code=403, detail="Acesso negado a este relatório")
    return rd


@router.get("")
async def list_reports(user: CurrentUser = Depends(get_current_user)) -> dict:
    items = [
        {
            "key": rd.key, "title": rd.title, "description": rd.description,
            "category": rd.category, "icon": rd.icon, "supports_dates": rd.supports_dates,
            "summary": rd.summary,
        }
        for rd in rp.REPORTS.values()
        if has_capability(user.roles, rd.capability)
    ]
    # agrupa por categoria (preservando ordem de definição)
    cats: list[str] = []
    for it in items:
        if it["category"] not in cats:
            cats.append(it["category"])
    return {"categories": cats, "reports": items}


@router.get("/{key}/preview")
async def preview(
    key: str,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    _require_report(key, user)
    data = await rp.generate(session, key, _to_naive(date_from), _to_naive(date_to))
    # prévia limitada; a exportação traz tudo
    preview_rows = data["rows"][:200]
    return {**data, "rows": preview_rows, "preview_truncated": data["total"] > 200}


@router.post("/{key}/send-chat")
async def send_report_chat(
    key: str,
    webhook_id: int = Query(...),
    request: Request = None,  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Envia um resumo do relatório para um canal do Google Chat (ação ativa)."""
    _require_report(key, user)
    from app.services.chatops import send_report_to_chat

    result = await send_report_to_chat(session, key, webhook_id)
    await record_audit(
        session, actor=user.username, actor_role=user.role, action="report_to_chat",
        resource=f"report:{key}:webhook:{webhook_id}", success=result.get("ok", False),
        ip_address=request.client.host if request and request.client else None,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("message", "Falha no envio"))
    return result


@router.post("/export")
async def export_report(
    request: Request,
    key: str = Query(...),
    fmt: str = Query("csv", pattern="^(csv|json)$"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    rd = _require_report(key, user)
    data = await rp.generate(session, key, _to_naive(date_from), _to_naive(date_to))
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    await record_audit(
        session, actor=user.username, actor_role=user.role, action="export",
        resource=f"report:{key}:{fmt}",
        ip_address=request.client.host if request.client else None,
        detail={"rows": data["total"], "format": fmt},
    )

    fields = [c["field"] for c in data["columns"]]
    headers_map = {c["field"]: c["header"] for c in data["columns"]}

    if fmt == "json":
        import json

        payload = json.dumps(data, ensure_ascii=False, default=str, indent=2)
        return StreamingResponse(
            iter([payload]), media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={key}_{stamp}.json"},
        )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([headers_map[f] for f in fields])
    for row in data["rows"]:
        writer.writerow([row.get(f, "") for f in fields])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={key}_{stamp}.csv"},
    )
