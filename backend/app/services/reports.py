"""Registro e geração de relatórios. Somente leitura.

Cada relatório define título, descrição, categoria, colunas e um provedor de
dados. Usado por /reports (lista), /reports/{key}/preview (prévia + HTML) e
/reports/export (CSV/JSON). Reusa serviços de detecção/postura/inventário.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.directory import ADGroup, ADUser
from app.models.enums import EventType
from app.models.event import NormalizedEvent
from app.models.ops import InternalAuditLog

settings = get_settings()


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class ReportDef:
    key: str
    title: str
    description: str
    category: str
    icon: str
    columns: list[tuple[str, str]]           # (campo, cabeçalho)
    provider: Callable
    supports_dates: bool = False
    capability: str = "report:export"
    summary: bool = False                    # relatório com bloco de resumo
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Provedores de dados (retornam {"rows": [...], "summary": {...}?})
# ---------------------------------------------------------------------------
def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


async def _events(session, types, date_from, date_to, extra=None, limit=50000):
    stmt = select(NormalizedEvent).where(NormalizedEvent.event_type.in_(types))
    if extra is not None:
        stmt = stmt.where(extra)
    if date_from:
        stmt = stmt.where(NormalizedEvent.event_time_utc >= date_from)
    if date_to:
        stmt = stmt.where(NormalizedEvent.event_time_utc <= date_to)
    stmt = stmt.order_by(NormalizedEvent.event_time_utc.desc()).limit(limit)
    return (await session.execute(stmt)).scalars().all()


async def prov_lockouts(session, date_from, date_to, _f):
    rows = await _events(session, [EventType.account_lockout], date_from, date_to)
    return {"rows": [
        {"time": _iso(e.event_time_utc), "target_username": e.target_username,
         "domain_controller": e.domain_controller, "caller_computer": e.caller_computer,
         "source_ip": e.source_ip, "auth": e.authentication_package, "risk_score": e.risk_score}
        for e in rows]}


async def prov_failed_logons(session, date_from, date_to, _f):
    rows = await _events(
        session,
        [EventType.failed_logon, EventType.kerberos_preauth_failed, EventType.ntlm_validation],
        date_from, date_to)
    return {"rows": [
        {"time": _iso(e.event_time_utc), "event_id": e.event_id, "target_username": e.target_username,
         "domain_controller": e.domain_controller, "caller_computer": e.caller_computer,
         "source_ip": e.source_ip, "failure_reason": e.failure_reason}
        for e in rows]}


async def prov_password_events(session, date_from, date_to, _f):
    rows = await _events(session, [EventType.password_change, EventType.password_reset], date_from, date_to)
    return {"rows": [
        {"time": _iso(e.event_time_utc),
         "tipo": "Reset (operador)" if e.event_type == EventType.password_reset else "Troca (próprio)",
         "target_username": e.target_username, "actor_username": e.actor_username,
         "domain_controller": e.domain_controller}
        for e in rows]}


async def prov_privileged_changes(session, date_from, date_to, _f):
    rows = await _events(
        session, [EventType.group_member_added, EventType.group_member_removed],
        date_from, date_to, extra=NormalizedEvent.is_privileged_target.is_(True))
    return {"rows": [
        {"time": _iso(e.event_time_utc),
         "acao": "Adição" if e.event_type == EventType.group_member_added else "Remoção",
         "grupo": e.target_username, "por": e.actor_username, "dc": e.domain_controller}
        for e in rows]}


async def prov_attack_surface(session, _df, _dt, _f):
    from app.services import detections
    out = []
    for cat, fn in (("Kerberoasting", detections.kerberoasting),
                    ("AS-REP Roasting", detections.asrep_roasting),
                    ("Stale Admin", detections.stale_admins)):
        res = await fn(session)
        for i in res["items"]:
            out.append({"categoria": cat, "sam_account_name": i["sam_account_name"],
                        "display_name": i.get("display_name"), "risk_score": i["risk_score"],
                        "motivos": "; ".join(i["reasons"])})
    out.sort(key=lambda x: x["risk_score"], reverse=True)
    return {"rows": out}


async def prov_service_accounts(session, _df, _dt, _f):
    stmt = select(ADUser).where(
        func.jsonb_array_length(func.cast(ADUser.service_principal_name, JSONB)) > 0
    ).order_by(ADUser.is_privileged.desc())
    rows = (await session.execute(stmt)).scalars().all()
    return {"rows": [
        {"sam_account_name": u.sam_account_name, "display_name": u.display_name,
         "spn": "; ".join(u.service_principal_name[:3]), "spn_count": len(u.service_principal_name),
         "privilegiada": u.is_privileged, "pwd_last_set": _iso(u.pwd_last_set),
         "senha_nunca_expira": u.password_never_expires}
        for u in rows]}


async def prov_password_hygiene(session, _df, _dt, _f):
    now = _naive_now()
    out = []
    # a expirar (<=14d)
    exp = (await session.execute(select(ADUser).where(and_(
        ADUser.password_expires_at.is_not(None), ADUser.password_expires_at >= now,
        ADUser.password_expires_at <= now + timedelta(days=14), ADUser.is_disabled.is_(False)
    )))).scalars().all()
    for u in exp:
        out.append({"sam_account_name": u.sam_account_name, "display_name": u.display_name,
                    "situacao": "Senha a expirar (≤14d)", "detalhe": _iso(u.password_expires_at)})
    # nunca expira
    nev = (await session.execute(select(ADUser).where(ADUser.password_never_expires.is_(True)).limit(5000))).scalars().all()
    for u in nev:
        out.append({"sam_account_name": u.sam_account_name, "display_name": u.display_name,
                    "situacao": "Senha nunca expira", "detalhe": ""})
    # password not required
    pnr = (await session.execute(select(ADUser).where(ADUser.password_not_required.is_(True)))).scalars().all()
    for u in pnr:
        out.append({"sam_account_name": u.sam_account_name, "display_name": u.display_name,
                    "situacao": "Password Not Required", "detalhe": ""})
    return {"rows": out}


async def prov_inactive(session, _df, _dt, _f):
    stmt = select(ADUser).where(and_(ADUser.is_inactive.is_(True), ADUser.is_disabled.is_(False))).limit(5000)
    rows = (await session.execute(stmt)).scalars().all()
    return {"rows": [
        {"sam_account_name": u.sam_account_name, "display_name": u.display_name,
         "departamento": u.department, "ultimo_logon": _iso(u.last_logon_timestamp),
         "privilegiada": u.is_privileged}
        for u in rows]}


async def prov_privileged_groups(session, _df, _dt, _f):
    import re
    stmt = select(ADGroup).where(ADGroup.is_privileged.is_(True)).order_by(ADGroup.member_count.desc())
    rows = (await session.execute(stmt)).scalars().all()
    out = []
    for g in rows:
        members = [(m.group(1) if (m := re.match(r"CN=([^,]+)", dn)) else dn) for dn in (g.members or [])]
        out.append({"grupo": g.sam_account_name, "descricao": g.description,
                    "membros": g.member_count, "lista": "; ".join(members[:20])})
    return {"rows": out}


async def prov_portal_audit(session, date_from, date_to, _f):
    stmt = select(InternalAuditLog)
    if date_from:
        stmt = stmt.where(InternalAuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(InternalAuditLog.created_at <= date_to)
    stmt = stmt.order_by(InternalAuditLog.created_at.desc()).limit(20000)
    rows = (await session.execute(stmt)).scalars().all()
    return {"rows": [
        {"time": _iso(r.created_at), "ator": r.actor, "perfil": r.actor_role,
         "acao": r.action, "recurso": r.resource, "ip": r.ip_address, "sucesso": r.success}
        for r in rows]}


async def prov_posture(session, _df, _dt, _f):
    from app.services.posture import compute_posture_counts, compute_security_score
    score = await compute_security_score(session)
    counts = await compute_posture_counts(session)
    rows = [{"fator": fdef["label"], "quantidade": fdef["count"], "impacto": fdef["impact"],
             "severidade": fdef["severity"]} for fdef in score["factors"]]
    return {"rows": rows, "summary": {
        "score": score["score"], "grade": score["grade"],
        "total_usuarios": counts.get("total_users"), "privilegiadas": counts.get("privileged"),
        "senha_nunca_expira": counts.get("never_expires"), "inativas": counts.get("inactive"),
        "spn": counts.get("spn"), "asrep": counts.get("asrep"),
        "maquinas_legado": counts.get("legacy_machines"),
    }}


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------
REPORTS: dict[str, ReportDef] = {
    r.key: r for r in [
        ReportDef("security_posture", "Postura Executiva do AD",
                  "Security Score, nota A–F e fatores de risco consolidados.",
                  "Executivo", "posture",
                  [("fator", "Fator"), ("quantidade", "Qtd."), ("impacto", "Impacto"), ("severidade", "Severidade")],
                  prov_posture, summary=True, capability="dashboard:read"),
        ReportDef("attack_surface", "Superfície de Ataque",
                  "Kerberoasting, AS-REP Roasting e contas administrativas de risco.",
                  "Segurança", "target",
                  [("categoria", "Categoria"), ("sam_account_name", "Conta"), ("display_name", "Nome"),
                   ("risk_score", "Risco"), ("motivos", "Motivos")],
                  prov_attack_surface, capability="critical:read"),
        ReportDef("service_accounts", "Contas de Serviço e SPN",
                  "Contas com servicePrincipalName (alvo de Kerberoasting).",
                  "Segurança", "lock",
                  [("sam_account_name", "Conta"), ("display_name", "Nome"), ("spn", "SPN"),
                   ("spn_count", "Qtd SPN"), ("privilegiada", "Priv."), ("pwd_last_set", "Últ. senha"),
                   ("senha_nunca_expira", "Senha ∞")],
                  prov_service_accounts, capability="critical:read"),
        ReportDef("password_hygiene", "Higiene de Senhas e Identidades",
                  "Senhas a expirar, nunca-expira e Password Not Required.",
                  "Identidade", "user",
                  [("sam_account_name", "Conta"), ("display_name", "Nome"), ("situacao", "Situação"),
                   ("detalhe", "Detalhe")],
                  prov_password_hygiene),
        ReportDef("inactive_accounts", "Contas Inativas",
                  "Contas habilitadas sem logon recente.",
                  "Identidade", "users",
                  [("sam_account_name", "Conta"), ("display_name", "Nome"), ("departamento", "Depto"),
                   ("ultimo_logon", "Últ. logon"), ("privilegiada", "Priv.")],
                  prov_inactive),
        ReportDef("privileged_groups", "Grupos Privilegiados",
                  "Grupos privilegiados e seus membros.",
                  "Identidade", "groups",
                  [("grupo", "Grupo"), ("descricao", "Descrição"), ("membros", "Membros"), ("lista", "Lista")],
                  prov_privileged_groups),
        ReportDef("lockouts", "Bloqueios de Conta",
                  "Eventos 4740 com origem e risco.",
                  "Eventos", "lock",
                  [("time", "Data/Hora"), ("target_username", "Usuário"), ("domain_controller", "DC"),
                   ("caller_computer", "Origem"), ("source_ip", "IP"), ("auth", "Auth"), ("risk_score", "Risco")],
                  prov_lockouts, supports_dates=True, capability="lockout:read"),
        ReportDef("failed_logons", "Falhas de Autenticação",
                  "Eventos 4625/4771/4776.",
                  "Eventos", "alert",
                  [("time", "Data/Hora"), ("event_id", "Event ID"), ("target_username", "Usuário"),
                   ("domain_controller", "DC"), ("caller_computer", "Origem"), ("source_ip", "IP"),
                   ("failure_reason", "Motivo")],
                  prov_failed_logons, supports_dates=True),
        ReportDef("password_events", "Trocas e Resets de Senha",
                  "Eventos 4723/4724.",
                  "Eventos", "report",
                  [("time", "Data/Hora"), ("tipo", "Tipo"), ("target_username", "Usuário"),
                   ("actor_username", "Executado por"), ("domain_controller", "DC")],
                  prov_password_events, supports_dates=True),
        ReportDef("privileged_changes", "Mudanças em Grupos Privilegiados",
                  "Adições/remoções em grupos privilegiados.",
                  "Eventos", "groups",
                  [("time", "Data/Hora"), ("acao", "Ação"), ("grupo", "Grupo"), ("por", "Por"), ("dc", "DC")],
                  prov_privileged_changes, supports_dates=True),
        ReportDef("portal_audit", "Auditoria do Portal",
                  "Logins, MFA, exportações, acessos a JSON bruto e ações ativas.",
                  "Conformidade", "report",
                  [("time", "Data/Hora"), ("ator", "Ator"), ("perfil", "Perfil"), ("acao", "Ação"),
                   ("recurso", "Recurso"), ("ip", "IP"), ("sucesso", "OK")],
                  prov_portal_audit, supports_dates=True, capability="critical:read"),
    ]
}


async def generate(session: AsyncSession, key: str, date_from=None, date_to=None, filters=None) -> dict:
    rd = REPORTS.get(key)
    if not rd:
        raise KeyError(key)
    data = await rd.provider(session, date_from, date_to, filters or {})
    rows = data["rows"]
    return {
        "key": rd.key, "title": rd.title, "category": rd.category,
        "columns": [{"field": f, "header": h} for f, h in rd.columns],
        "rows": rows, "total": len(rows),
        "summary": data.get("summary"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
