"""Testes das conversões de atributos do AD (FILETIME, SID, GUID, UAC)."""
from datetime import datetime, timezone

from app.ldap.converters import (
    UAC_ACCOUNTDISABLE,
    UAC_DONT_EXPIRE_PASSWORD,
    filetime_to_datetime,
    guid_to_string,
    parse_uac,
    sid_to_string,
)


def test_filetime_never_returns_none():
    assert filetime_to_datetime(0) is None
    assert filetime_to_datetime(0x7FFFFFFFFFFFFFFF) is None
    assert filetime_to_datetime(None) is None


def test_filetime_known_value():
    # 2021-01-01T00:00:00Z em FILETIME = (1609459200 + 11644473600) * 1e7
    dt = filetime_to_datetime(132539328000000000)
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2021 and dt.month == 1 and dt.day == 1


def test_sid_binary_to_string():
    # S-1-5-21-... exemplo binário conhecido (BUILTIN\Administrators = S-1-5-32-544)
    raw = bytes([1, 2, 0, 0, 0, 0, 0, 5, 0x20, 0, 0, 0, 0x20, 2, 0, 0])
    assert sid_to_string(raw) == "S-1-5-32-544"


def test_sid_passthrough_string():
    assert sid_to_string("S-1-5-21-1") == "S-1-5-21-1"


def test_guid_roundtrip():
    import uuid

    u = uuid.uuid4()
    assert guid_to_string(u.bytes_le) == str(u)


def test_parse_uac_flags():
    flags = parse_uac(UAC_ACCOUNTDISABLE | UAC_DONT_EXPIRE_PASSWORD)
    assert flags["is_disabled"] is True
    assert flags["password_never_expires"] is True
    assert flags["is_locked"] is False
