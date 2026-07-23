"""Configuração do collector (subconjunto do .env, com validação mínima)."""
from __future__ import annotations

import os


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _bool(key: str, default: bool = False) -> bool:
    return _env(key, str(default)).lower() in ("1", "true", "yes", "on")


def _int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _set(key: str, default: str) -> set[str]:
    return {x.strip() for x in _env(key, default).split(",") if x.strip()}


# Tipos "importantes" cujo JSON bruto vale a pena preservar (baixo volume, alto
# valor forense). Todo o resto tem o raw_event_json descartado por padrão.
_DEFAULT_RAW_TYPES = (
    "account_lockout,password_reset,password_change,user_created,user_deleted,"
    "group_member_added,group_member_removed,account_disabled,account_enabled,"
    "account_changed,account_renamed,account_unlocked,service_installed,"
    "ds_object_modified,ds_object_created,ds_object_deleted,special_privileges_assigned"
)
# Tipos descartados na ingestão (não são gravados). successful_logon (4624) é o
# maior gerador de volume em DCs e não é consumido por nenhuma tela/relatório.
_DEFAULT_DROP_TYPES = "successful_logon"


class CollectorConfig:
    database_url = _env("DATABASE_URL")
    mode = _env("EVENT_COLLECTOR_MODE", "wef").lower()
    enabled = _bool("EVENT_COLLECTOR_ENABLED", True)
    batch_size = _int("EVENT_BATCH_SIZE", 500)
    poll_interval = _int("EVENT_POLL_INTERVAL_SECONDS", 60)

    # ---- Política de armazenamento (controle de volume/tamanho do banco) ----
    # Guardar o JSON bruto de todos os eventos? Padrão: não (só dos importantes).
    store_raw = _bool("EVENT_STORE_RAW", False)
    store_raw_types = _set("EVENT_STORE_RAW_TYPES", _DEFAULT_RAW_TYPES)
    # Tipos ignorados por completo na ingestão (nem são gravados).
    drop_types = _set("EVENT_DROP_TYPES", _DEFAULT_DROP_TYPES)

    # WEF
    wef_enabled = _bool("WEF_ENABLED", True)
    wef_log_name = _env("WEF_LOG_NAME", "ForwardedEvents")
    # Diretório-spool onde os eventos encaminhados são despejados como NDJSON
    # (o subscription do Windows Event Collector -> exportador -> arquivo).
    wef_spool_dir = _env("WEF_SPOOL_DIR", "/data/wef-spool")

    # WinRM (alternativo)
    winrm_enabled = _bool("WINRM_ENABLED", False)
    winrm_username = _env("WINRM_USERNAME")
    winrm_password = _env("WINRM_PASSWORD")
    winrm_transport = _env("WINRM_TRANSPORT", "ntlm")
    winrm_use_ssl = _bool("WINRM_USE_SSL", True)
    winrm_port = _int("WINRM_PORT", 5986)
    winrm_verify_tls = _bool("WINRM_VERIFY_TLS", True)
    winrm_dcs = [d.strip() for d in _env("WINRM_DOMAIN_CONTROLLERS").split(",") if d.strip()]

    # SIEM alternativos
    elastic_url = _env("ELASTIC_URL")
    elastic_api_key = _env("ELASTIC_API_KEY")
    elastic_index = _env("ELASTIC_INDEX", "winlogbeat-*")
    graylog_api_url = _env("GRAYLOG_API_URL")
    graylog_api_token = _env("GRAYLOG_API_TOKEN")
    splunk_api_url = _env("SPLUNK_API_URL")
    splunk_api_token = _env("SPLUNK_API_TOKEN")
    wazuh_api_url = _env("WAZUH_API_URL")
    wazuh_api_user = _env("WAZUH_API_USER")
    wazuh_api_password = _env("WAZUH_API_PASSWORD")

    log_level = _env("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> None:
        if not cls.database_url:
            raise RuntimeError("DATABASE_URL é obrigatória para o collector")
        valid_modes = {"wef", "winrm", "elastic", "wazuh", "graylog", "splunk", "api"}
        if cls.mode not in valid_modes:
            raise RuntimeError(
                f"EVENT_COLLECTOR_MODE inválido: {cls.mode}. Use um de {valid_modes}"
            )


config = CollectorConfig
