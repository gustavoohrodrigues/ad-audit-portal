"""Logging estruturado em JSON com redação de segredos.

Regra crítica: senha, token, segredo, chave privada ou connection string
completa NUNCA devem aparecer nos logs. ``_redact`` filtra chaves sensíveis
e mascara connection strings antes da serialização.
"""
from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, timezone

try:
    import orjson

    def _dumps(obj: dict) -> str:
        return orjson.dumps(obj).decode()
except ImportError:  # fallback
    import json

    def _dumps(obj: dict) -> str:
        return json.dumps(obj, default=str, ensure_ascii=False)


SENSITIVE_KEYS = re.compile(
    r"(pass|senha|secret|token|key|credential|authorization|cookie|bind_password)",
    re.IGNORECASE,
)
# mascara user:pass@host em URLs (postgres://, redis://, ldaps://…)
_CONN_RE = re.compile(r"(?P<scheme>[a-z0-9+]+://)(?P<user>[^:/@]+):(?P<pw>[^@/]+)@")


def redact_value(value: str) -> str:
    return _CONN_RE.sub(lambda m: f"{m.group('scheme')}{m.group('user')}:***@", value)


def _redact(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if SENSITIVE_KEYS.search(k):
            out[k] = "***"
        elif isinstance(v, str):
            out[k] = redact_value(v)
        elif isinstance(v, dict):
            out[k] = _redact(v)
        else:
            out[k] = v
    return out


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact_value(record.getMessage()),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(_redact(extra))
        return _dumps(payload)


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
        )
    root.addHandler(handler)
    root.setLevel(level.upper())
    # silencia libs verbosas
    for noisy in ("uvicorn.access", "ldap3"):
        logging.getLogger(noisy).setLevel("WARNING")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
