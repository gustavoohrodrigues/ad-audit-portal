"""Gera dados MOCK para ambiente de demonstração (NÃO usar em produção).

Popula usuários, DCs, fontes, eventos normalizados (bloqueios, falhas, resets,
mudanças de grupo), investigações de bloqueio e alertas — tudo fictício.

Uso:  python -m app.seed_mock
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.database import SessionLocal, init_models
from app.models.directory import ADUser, DomainController
from app.models.enums import (
    AlertStatus,
    EventType,
    InvestigationStatus,
    Severity,
    SourceStatus,
)
from app.models.event import NormalizedEvent
from app.models.ops import Alert, EventSource, LockoutInvestigation
from app.services.risk import score_event

# semente fixa para reprodutibilidade do ambiente demo
random.seed(42)

DCS = ["DC01", "DC02", "DC03"]
COMPUTERS = ["NB-FINANCE-07", "WS-RH-12", "SRV-APP-01", "NB-TI-03", "SRV-BACKUP-01"]
USERS = [
    ("jsilva", "João Silva", "joao.silva@empresa.local", "Financeiro", False, False),
    ("maria.souza", "Maria Souza", "maria.souza@empresa.local", "RH", False, False),
    ("administrator", "Administrator", "admin@empresa.local", "TI", True, True),
    ("svc_backup", "Serviço Backup", None, "TI", True, True),
    ("pedro.admin", "Pedro Admin", "pedro.admin@empresa.local", "TI", True, False),
    ("ana.costa", "Ana Costa", "ana.costa@empresa.local", "Comercial", False, False),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def seed() -> None:
    await init_models()
    async with SessionLocal() as s:
        # limpa tabelas voláteis do demo
        for model in (Alert, LockoutInvestigation, NormalizedEvent, EventSource,
                      DomainController, ADUser):
            await s.execute(delete(model))
        await s.commit()

        # DCs
        for i, dc in enumerate(DCS):
            s.add(DomainController(
                hostname=f"{dc}.empresa.local",
                domain="empresa.local",
                ip_address=f"10.0.0.{10 + i}",
                status=SourceStatus.healthy,
                last_event_at=_now() - timedelta(minutes=random.randint(1, 15)),
                last_heartbeat_at=_now(),
                event_count_24h=random.randint(500, 3000),
                ingestion_lag_seconds=random.randint(2, 40),
            ))

        # fonte WEF
        s.add(EventSource(
            name="WEF-ForwardedEvents",
            connector_type="wef",
            endpoint="wef-collector.empresa.local:5985",
            enabled=True,
            status=SourceStatus.healthy,
            last_event_at=_now() - timedelta(minutes=2),
            last_heartbeat_at=_now(),
            events_ingested=45231,
            errors_count=12,
        ))

        # usuários
        for sam, name, mail, dept, priv, crit in USERS:
            s.add(ADUser(
                object_sid=f"S-1-5-21-1111-2222-3333-{random.randint(1000,9999)}",
                sam_account_name=sam,
                user_principal_name=f"{sam}@empresa.local",
                display_name=name,
                mail=mail,
                department=dept,
                title="Analista" if not priv else "Administrador",
                distinguished_name=f"CN={name},OU=Usuarios,DC=empresa,DC=local",
                ou="OU=Usuarios,DC=empresa,DC=local",
                is_privileged=priv,
                is_critical=crit,
                password_never_expires=crit,
                pwd_last_set=_now() - timedelta(days=random.randint(10, 200)),
                last_logon_timestamp=_now() - timedelta(hours=random.randint(1, 100)),
                when_created=_now() - timedelta(days=random.randint(200, 1500)),
                risk_score=70 if priv else random.randint(0, 30),
                is_inactive=False,
            ))
        await s.commit()

        # eventos: bloqueios + falhas correlacionadas + resets + grupos
        events: list[NormalizedEvent] = []
        for _ in range(60):
            when = _now() - timedelta(hours=random.randint(0, 720))
            user = random.choice(USERS)
            dc = random.choice(DCS)
            caller = random.choice(COMPUTERS)
            etype = random.choices(
                [
                    EventType.account_lockout,
                    EventType.failed_logon,
                    EventType.password_reset,
                    EventType.password_change,
                    EventType.group_member_added,
                    EventType.account_changed,
                ],
                weights=[3, 6, 2, 2, 1, 2],
            )[0]
            priv = user[4]
            score, sev = score_event(
                event_type=etype,
                event_time=when,
                is_privileged_target=priv,
                is_critical_account=user[5],
                privileged_group_change=(etype == EventType.group_member_added and priv),
            )
            ev = NormalizedEvent(
                event_time_utc=when,
                event_record_id=random.randint(100000, 999999),
                event_id={
                    EventType.account_lockout: 4740,
                    EventType.failed_logon: 4625,
                    EventType.password_reset: 4724,
                    EventType.password_change: 4723,
                    EventType.group_member_added: 4732,
                    EventType.account_changed: 4738,
                }[etype],
                event_type=etype,
                severity=sev,
                risk_score=score,
                domain="empresa.local",
                domain_controller=f"{dc}.empresa.local",
                target_username=user[0],
                target_upn=f"{user[0]}@empresa.local",
                caller_computer=caller if etype in (
                    EventType.account_lockout, EventType.failed_logon) else None,
                source_ip=f"10.10.{random.randint(1,50)}.{random.randint(2,254)}",
                actor_username="pedro.admin" if etype in (
                    EventType.password_reset, EventType.group_member_added) else None,
                authentication_package=random.choice(["Kerberos", "NTLM"]),
                failure_reason="0xC000006A" if etype == EventType.failed_logon else None,
                is_privileged_target=priv,
                is_critical_account=user[5],
                raw_event_json={"demo": True, "EventID": 0, "Computer": f"{dc}.empresa.local"},
            )
            events.append(ev)
            s.add(ev)
        await s.commit()

        # investigações a partir dos bloqueios
        for ev in events:
            if ev.event_type == EventType.account_lockout:
                await s.refresh(ev)
                s.add(LockoutInvestigation(
                    event_id=ev.id,
                    target_username=ev.target_username,
                    target_sid=ev.target_sid,
                    lockout_time_utc=ev.event_time_utc,
                    domain_controller=ev.domain_controller,
                    caller_computer=ev.caller_computer,
                    source_ip=ev.source_ip,
                    auth_type=ev.authentication_package,
                    lockouts_24h=random.randint(1, 5),
                    lockouts_same_source=random.randint(1, 3),
                    status=random.choice(list(InvestigationStatus)),
                ))

        # alertas
        for sev in [Severity.critical, Severity.high, Severity.medium]:
            for _ in range(random.randint(1, 3)):
                s.add(Alert(
                    title=f"Evento de risco {sev.value}",
                    description="Alerta gerado pelo motor de risco (demo).",
                    severity=sev,
                    risk_score={"critical": 95, "high": 80, "medium": 60}[sev.value],
                    status=AlertStatus.open,
                    target_username=random.choice(USERS)[0],
                ))
        await s.commit()
    print("Dados mock inseridos com sucesso.")


if __name__ == "__main__":
    asyncio.run(seed())
