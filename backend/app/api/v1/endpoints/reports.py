"""Relatórios e exportação (RBAC: report:export). Exportações são auditadas."""
from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.models.enums import EventType
from app.models.event import NormalizedEvent
from app.models.ops import ReportExport
from app.schemas import ReportExportRequest
from app.services.audit import record_audit

router = APIRouter(prefix="/reports", tags=["reports"])

REPORT_TYPES = {
    "lockouts": [EventType.account_lockout],
    "password_events": [EventType.password_change, EventType.password_reset],
    "privileged_changes": [
        EventType.group_member_added,
        EventType.group_member_removed,
    ],
    "events": None,
}


@router.get("")
async def list_reports(
    user: CurrentUser = Depends(require_capability("report:export")),
) -> dict:
    return {"available": list(REPORT_TYPES.keys()), "formats": ["csv", "json"]}


@router.post("/export")
async def export_report(
    payload: ReportExportRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("report:export")),
) -> StreamingResponse:
    types = REPORT_TYPES.get(payload.report_type)
    stmt = select(NormalizedEvent)
    if types:
        stmt = stmt.where(NormalizedEvent.event_type.in_(types))
    if payload.date_from:
        stmt = stmt.where(NormalizedEvent.event_time_utc >= payload.date_from)
    if payload.date_to:
        stmt = stmt.where(NormalizedEvent.event_time_utc <= payload.date_to)
    stmt = stmt.order_by(NormalizedEvent.event_time_utc.desc()).limit(50000)
    rows = (await session.execute(stmt)).scalars().all()

    cols = [
        "event_time_utc", "event_id", "event_type", "severity", "risk_score",
        "domain_controller", "target_username", "actor_username",
        "caller_computer", "source_ip", "failure_reason",
    ]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(cols)
    for e in rows:
        writer.writerow([getattr(e, c) for c in cols])
    buf.seek(0)

    session.add(
        ReportExport(
            report_type=payload.report_type,
            format="csv",
            requested_by=user.username,
            parameters=payload.model_dump(mode="json"),
            row_count=len(rows),
            status="completed",
        )
    )
    await session.commit()
    await record_audit(
        session,
        actor=user.username,
        actor_role=user.role,
        action="export",
        resource=f"report:{payload.report_type}",
        ip_address=request.client.host if request.client else None,
        detail={"rows": len(rows), "format": "csv"},
    )
    fname = f"{payload.report_type}_{datetime.utcnow():%Y%m%d_%H%M%S}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )
