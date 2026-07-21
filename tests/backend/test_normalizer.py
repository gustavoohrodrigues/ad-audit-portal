"""Testes do normalizador de eventos do collector.

O collector e o backend usam o mesmo nome de pacote (`app`), então carregamos
o módulo do collector diretamente pelo caminho de arquivo para evitar colisão.
"""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[2] / "collector" / "app" / "normalizer.py"
_spec = importlib.util.spec_from_file_location("collector_normalizer", _path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
EVENT_ID_MAP = _mod.EVENT_ID_MAP
normalize = _mod.normalize


def _event_4740():
    return {
        "System": {
            "EventID": 4740,
            "Computer": "DC01.empresa.local",
            "EventRecordID": 123456,
            "TimeCreated": "2026-07-20T10:15:00Z",
        },
        "EventData": {
            "TargetUserName": "jsilva",
            "TargetDomainName": "EMPRESA",
            "CallerComputerName": "NB-FINANCE-07",
        },
    }


def test_lockout_normalization():
    n = normalize(_event_4740(), collector_source="wef")
    assert n is not None
    assert n["event_type"] == "account_lockout"
    assert n["event_id"] == 4740
    assert n["target_username"] == "jsilva"
    assert n["domain_controller"] == "DC01.empresa.local"
    assert n["caller_computer"] == "NB-FINANCE-07"
    assert n["event_record_id"] == 123456


def test_unknown_event_id_is_ignored():
    ev = _event_4740()
    ev["System"]["EventID"] = 9999
    assert normalize(ev) is None


def test_privileged_group_change_flagged():
    ev = {
        "System": {"EventID": 4732, "Computer": "DC01", "EventRecordID": 1},
        "EventData": {"TargetUserName": "Domain Admins", "SubjectUserName": "admin"},
    }
    n = normalize(ev)
    assert n["event_type"] == "group_member_added"
    assert n["is_privileged_target"] is True


def test_all_required_event_ids_mapped():
    required = {4624, 4625, 4720, 4722, 4723, 4724, 4725, 4726, 4728, 4732,
                4756, 4729, 4733, 4757, 4738, 4740, 4767, 4771, 4776, 4781,
                5136, 5137, 5141}
    assert required.issubset(set(EVENT_ID_MAP))


def test_loopback_ip_cleaned():
    ev = _event_4740()
    ev["EventData"]["IpAddress"] = "::1"
    n = normalize(ev)
    assert n["source_ip"] is None
