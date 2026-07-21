"""Painel de investigação de bloqueios (Event 4740). SOMENTE LEITURA no AD —
não há endpoint de desbloqueio."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.models.event import NormalizedEvent
from app.models.ops import LockoutInvestigation, TicketLink
from app.schemas import LockoutOut, NoteCreate, TicketLinkCreate
from app.services.audit import record_audit

router = APIRouter(prefix="/lockouts", tags=["lockouts"])

# Hipóteses técnicas oferecidas na investigação (checklist do analista).
LOCKOUT_HYPOTHESES = [
    "Credencial antiga em notebook/desktop",
    "Credential Manager",
    "Outlook ou dispositivo móvel",
    "Unidade de rede mapeada",
    "Tarefa agendada",
    "Serviço Windows com credencial antiga",
    "Application Pool IIS",
    "Serviço de backup",
    "VPN",
    "Aplicação legada",
    "Impressora / NAS / equipamento externo",
]

# Playbook guiado: passos com evidência sugerida (checklist com status por item).
LOCKOUT_PLAYBOOK = [
    {"id": "caller", "title": "Identificar o Caller Computer Name",
     "evidence": "Campo caller_computer do 4740; correlacionar com 4625/4771/4776."},
    {"id": "credman", "title": "Verificar Credential Manager na origem",
     "evidence": "cmdkey /list na estação de origem; remover credenciais antigas."},
    {"id": "mobile", "title": "Checar Outlook/celular/ActiveSync",
     "evidence": "Dispositivos móveis com senha antiga geram bloqueio recorrente."},
    {"id": "mapped", "title": "Unidades de rede mapeadas",
     "evidence": "net use na origem; mapeamentos com credencial explícita."},
    {"id": "task", "title": "Tarefas agendadas com credencial",
     "evidence": "schtasks /query /v; tarefas 'Run as' com senha antiga."},
    {"id": "service", "title": "Serviços Windows / App Pool IIS",
     "evidence": "services.msc e IIS AppPool com identidade de conta antiga."},
    {"id": "backup", "title": "Agentes de backup / VPN / apps legadas",
     "evidence": "Verificar agentes e VPN usando a credencial da conta."},
    {"id": "external", "title": "Impressora / NAS / equipamento externo",
     "evidence": "Equipamentos com credencial fixa cacheada."},
]


@router.get("", response_model=list[LockoutOut])
async def list_lockouts(
    status: str | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("lockout:read")),
) -> list[LockoutOut]:
    stmt = select(LockoutInvestigation)
    if status:
        stmt = stmt.where(LockoutInvestigation.status == status)
    stmt = stmt.order_by(LockoutInvestigation.lockout_time_utc.desc()).limit(min(limit, 500))
    rows = (await session.execute(stmt)).scalars().all()
    return [LockoutOut.model_validate(r) for r in rows]


@router.get("/hypotheses")
async def hypotheses(
    user: CurrentUser = Depends(require_capability("lockout:read")),
) -> dict:
    return {"hypotheses": LOCKOUT_HYPOTHESES}


@router.get("/{lockout_id}")
async def get_lockout(
    lockout_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("lockout:read")),
) -> dict:
    inv = await session.get(LockoutInvestigation, lockout_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigação não encontrada")
    correlated = []
    if inv.correlated_event_ids:
        stmt = select(NormalizedEvent).where(
            NormalizedEvent.id.in_(inv.correlated_event_ids)
        )
        correlated = [
            {
                "id": e.id,
                "event_id": e.event_id,
                "type": e.event_type,
                "time": e.event_time_utc,
                "source_ip": e.source_ip,
                "caller": e.caller_computer,
                "auth": e.authentication_package,
                "failure": e.failure_reason,
            }
            for e in (await session.execute(stmt)).scalars().all()
        ]
    return {
        "investigation": LockoutOut.model_validate(inv).model_dump(),
        "correlated_events": correlated,
        "hypotheses": LOCKOUT_HYPOTHESES,
        "playbook": LOCKOUT_PLAYBOOK,
        "playbook_state": inv.playbook_state or {},
    }


@router.post("/{lockout_id}/notes", response_model=LockoutOut)
async def add_note(
    lockout_id: int,
    payload: NoteCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("note:write")),
) -> LockoutOut:
    inv = await session.get(LockoutInvestigation, lockout_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigação não encontrada")
    inv.analyst_note = payload.note
    if payload.root_cause is not None:
        inv.root_cause = payload.root_cause
    if payload.status is not None:
        inv.status = payload.status
    if payload.playbook_state is not None:
        inv.playbook_state = payload.playbook_state
    inv.assigned_to = user.username
    session.add(inv)
    await session.commit()
    await session.refresh(inv)
    await record_audit(
        session,
        actor=user.username,
        actor_role=user.role,
        action="lockout_note",
        resource=f"lockout:{lockout_id}",
        ip_address=request.client.host if request.client else None,
    )
    return LockoutOut.model_validate(inv)


@router.post("/{lockout_id}/link-ticket", response_model=LockoutOut)
async def link_ticket(
    lockout_id: int,
    payload: TicketLinkCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("ticket:link")),
) -> LockoutOut:
    inv = await session.get(LockoutInvestigation, lockout_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigação não encontrada")
    inv.ticket_reference = payload.ticket_number
    inv.ticket_url = payload.ticket_url
    session.add(inv)
    session.add(
        TicketLink(
            system=payload.system,
            ticket_number=payload.ticket_number,
            ticket_url=payload.ticket_url,
            investigation_id=lockout_id,
            created_by=user.username,
        )
    )
    await session.commit()
    await session.refresh(inv)
    return LockoutOut.model_validate(inv)
