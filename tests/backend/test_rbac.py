"""Testes de RBAC: resolução de roles a partir de grupos AD e capacidades."""
from app.core.rbac import has_capability, highest_role, resolve_roles


def test_resolve_roles_from_group_dn():
    groups = [
        "CN=GG_AD_AUDIT_HELPDESK,OU=Grupos,DC=empresa,DC=local",
        "CN=Outro Grupo,OU=Grupos,DC=empresa,DC=local",
    ]
    roles = resolve_roles(groups)
    assert "helpdesk" in roles


def test_highest_role_precedence():
    roles = ["viewer", "helpdesk", "administrator"]
    assert highest_role(roles) == "administrator"


def test_viewer_cannot_read_raw_events():
    assert has_capability(["viewer"], "event:raw_read") is False


def test_security_analyst_can_read_raw_events():
    assert has_capability(["security_analyst"], "event:raw_read") is True


def test_admin_wildcard():
    assert has_capability(["administrator"], "anything:at:all") is True


def test_helpdesk_can_write_notes_not_export():
    assert has_capability(["helpdesk"], "note:write") is True
    assert has_capability(["helpdesk"], "report:export") is False
