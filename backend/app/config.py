"""Configuração central da aplicação.

Carrega as variáveis do arquivo .env com validação via Pydantic Settings.
Se variáveis OBRIGATÓRIAS estiverem ausentes ou inválidas, o backend recusa
iniciar e informa claramente o que falta (ver ``validate_required_settings``).

Nenhum segredo é registrado em log — ver ``safe_dump`` em ``core/logging.py``.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [v.strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(",") if v.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Aplicação ----
    app_name: str = "AD-Audit-Portal"
    app_env: Literal["production", "staging", "development"] = "production"
    app_debug: bool = False
    app_url: str = "https://ad-audit.local"
    app_timezone: str = "America/Sao_Paulo"
    app_secret_key: str = Field(min_length=16)
    jwt_secret_key: str = Field(min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    # ---- Frontend / CORS ----
    frontend_url: str = "https://ad-audit.local"
    cors_allowed_origins: str = ""
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str = ""

    # ---- PostgreSQL ----
    database_url: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "ad_audit"
    postgres_user: str = "ad_audit_app"
    postgres_password: str = ""

    # ---- Redis ----
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # ---- Active Directory / LDAP ----
    ad_enabled: bool = True
    ad_domain: str = ""
    ad_netbios_domain: str = ""
    ad_base_dn: str = ""
    ad_ldap_uri: str = ""
    ad_ldap_fallback_uri: str = ""
    ad_ldap_use_ssl: bool = True
    ad_ldap_tls_verify: bool = True
    ad_ldap_ca_cert_path: str = ""
    ad_ldap_timeout_seconds: int = 10
    ad_ldap_page_size: int = 500
    ad_bind_username: str = ""
    ad_bind_password: str = ""
    ad_bind_dn: str = ""
    ad_users_search_base: str = ""
    ad_computers_search_base: str = ""
    ad_groups_search_base: str = ""
    ad_service_accounts_search_base: str = ""
    ad_sync_enabled: bool = True
    ad_sync_interval_minutes: int = 60
    ad_sync_mode: Literal["full", "incremental"] = "full"
    ad_sync_usn_changed_enabled: bool = True

    # ---- Autenticação da aplicação ----
    auth_provider: Literal["ldap", "oidc", "saml"] = "ldap"
    auth_ldap_enabled: bool = True
    auth_ldap_uri: str = ""
    auth_ldap_base_dn: str = ""
    auth_ldap_user_search_base: str = ""
    auth_ldap_user_filter: str = "(&(objectClass=user)(sAMAccountName={username}))"
    auth_ldap_group_search_base: str = ""
    auth_group_viewers: str = "GG_AD_AUDIT_VIEWERS"
    auth_group_helpdesk: str = "GG_AD_AUDIT_HELPDESK"
    auth_group_security: str = "GG_AD_AUDIT_SECURITY"
    auth_group_admins: str = "GG_AD_AUDIT_ADMINS"

    # ---- Coleta de eventos ----
    event_collector_mode: str = "wef"
    event_collector_enabled: bool = True
    event_retention_days: int = 90
    event_raw_retention_days: int = 14
    event_batch_size: int = 500
    event_poll_interval_seconds: int = 60
    # Eventos de alto volume (ruído de autenticação) expurgados mais cedo.
    event_noise_retention_days: int = 14
    event_noise_types: str = (
        "failed_logon,ntlm_validation,kerberos_preauth_failed,successful_logon,"
        "kerberos_service_ticket,kerberos_tgt_request,kerberos_ticket_renewed,"
        "kerberos_service_ticket_failed,explicit_credential_logon"
    )
    wef_enabled: bool = True
    wef_host: str = ""
    wef_port: int = 5985
    wef_log_name: str = "ForwardedEvents"
    winrm_enabled: bool = False
    winrm_username: str = ""
    winrm_password: str = ""
    winrm_transport: str = "ntlm"
    winrm_use_ssl: bool = True
    winrm_port: int = 5986
    winrm_verify_tls: bool = True
    winrm_domain_controllers: str = ""

    # ---- Event IDs (CSV) ----
    event_ids_account_lockout: str = "4740"
    event_ids_password_change: str = "4723"
    event_ids_password_reset: str = "4724"
    event_ids_account_changed: str = "4738"
    event_ids_account_enabled: str = "4722"
    event_ids_account_disabled: str = "4725"
    event_ids_account_unlocked: str = "4767"
    event_ids_account_renamed: str = "4781"
    event_ids_user_created: str = "4720"
    event_ids_user_deleted: str = "4726"
    event_ids_group_member_added: str = "4728,4732,4756"
    event_ids_group_member_removed: str = "4729,4733,4757"
    event_ids_failed_logon: str = "4625,4771,4776"
    event_ids_successful_logon: str = "4624"
    event_ids_directory_service_changes: str = "5136,5137,5141"

    lockout_correlation_window_minutes: int = 30
    failed_logon_correlation_window_minutes: int = 15
    recurring_lockout_threshold: int = 3
    recurring_lockout_window_hours: int = 24

    # ---- Risco ----
    risk_scoring_enabled: bool = True
    risk_alert_threshold_medium: int = 50
    risk_alert_threshold_high: int = 75
    risk_alert_threshold_critical: int = 90
    business_hours_start: int = 8
    business_hours_end: int = 18
    privileged_groups: str = "Domain Admins,Enterprise Admins,Schema Admins,Administrators"
    critical_users: str = ""
    critical_ous: str = ""
    inactive_account_days: int = 90
    password_never_expires_alert: bool = True
    password_not_required_alert: bool = True
    sid_history_alert: bool = True
    delegation_alert: bool = True
    spn_change_alert: bool = True
    admin_count_alert: bool = True

    # ---- Alertas / Integrações ----
    alerts_enabled: bool = True
    alert_dedup_window_minutes: int = 60
    alert_email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""
    smtp_use_tls: bool = True
    webhook_enabled: bool = False
    webhook_url: str = ""
    webhook_token: str = ""
    glpi_enabled: bool = False
    glpi_url: str = ""
    glpi_app_token: str = ""
    glpi_user_token: str = ""
    glpi_entity_id: int = 0
    glpi_create_ticket_on_critical: bool = True
    glpi_dedup_window_hours: int = 24
    zabbix_enabled: bool = False
    zabbix_server: str = ""
    zabbix_host: str = "AD-Audit-Portal"
    zabbix_trapper_port: int = 10051
    prometheus_enabled: bool = True
    prometheus_metrics_path: str = "/metrics"

    # ---- Notificações / ações ativas ----
    notifications_enabled: bool = True
    # Domínio de e-mail forçado para destinatários da central de mensagens.
    notification_email_domain: str = "astra-sa.com"
    broadcast_max_recipients: int = 1000

    # ---- Scan de segurança (nmap) — ação ativa FORA do AD ----
    # Desabilitado por padrão; exige RBAC + confirmação + auditoria e SÓ varre
    # alvos na allowlist (CIDR/IP/hostname) ou DCs conhecidos.
    scan_enabled: bool = False
    scan_allowed_targets: str = ""            # CSV de CIDRs/IPs/hostnames
    scan_include_known_dcs: bool = True       # permite varrer DCs do inventário
    scan_nmap_timeout_seconds: int = 300
    scan_max_concurrent: int = 1
    scan_alerts_enabled: bool = True      # achados do scan viram alertas (sino)
    scan_findings_enabled: bool = True    # achados do scan viram findings normalizados

    # ---- Security Ops / Findings ----
    findings_ingest_max_bytes: int = 20_000_000   # limite do corpo de ingestão (anti-DoS)
    findings_max_page_size: int = 200
    google_chat_enabled: bool = True
    message_winrm_enabled: bool = False
    message_winrm_allowed_hosts: str = ""
    message_winrm_allow_any_host: bool = False
    message_winrm_timeout_seconds: int = 10
    password_expiry_notice_days: str = "14,7,3,1"
    password_expiry_notification_channel: str = "email"
    teams_enabled: bool = False
    teams_webhook_url: str = ""
    slack_enabled: bool = False
    slack_webhook_url: str = ""
    discord_enabled: bool = False
    discord_webhook_url: str = ""

    # ---- Segurança do portal ----
    mfa_required_roles: str = ""  # ex.: administrator,security_analyst
    auth_login_max_attempts: int = 5
    auth_login_lockout_minutes: int = 15

    # ---- Detecção ----
    password_spray_enabled: bool = True
    password_spray_window_minutes: int = 15
    password_spray_min_targets: int = 10
    kerberoasting_detection_enabled: bool = True
    asrep_roasting_detection_enabled: bool = True

    # ---- Auditoria interna ----
    audit_log_enabled: bool = True
    audit_log_retention_days: int = 730
    notification_retention_days: int = 180
    maintenance_vacuum_enabled: bool = True
    maintenance_cron_hour: int = 3
    db_statement_timeout_ms: int = 30000
    audit_export_enabled: bool = True
    audit_raw_event_access_security_only: bool = True
    mask_sensitive_data: bool = True

    # ---- Proxy / TLS (terminação no NPM externo) ----
    tls_enabled: bool = False

    # ---- Performance / pool / limites (Fase 1) ----
    api_sql_pool_size: int = 10
    api_sql_max_overflow: int = 20
    api_sql_pool_recycle_seconds: int = 1800
    api_max_page_size: int = 500
    api_default_event_range_days: int = 7
    api_max_event_range_days: int = 90

    # ---- Cache Redis ----
    cache_enabled: bool = True
    cache_dashboard_ttl_seconds: int = 60
    cache_entity_ttl_seconds: int = 300
    cache_search_ttl_seconds: int = 120
    cache_health_ttl_seconds: int = 30
    cache_stampede_lock_seconds: int = 10

    # ---- Feature flags ----
    feature_incidents_enabled: bool = False
    feature_performance_dashboard_enabled: bool = True
    feature_websocket_enabled: bool = False
    feature_partitioning_enabled: bool = False

    # ---- Rate limiting ----
    rate_limit_enabled: bool = True
    rate_limit_default: str = "120/minute"
    rate_limit_login: str = "10/minute"

    # ---- Backup ----
    backup_enabled: bool = True
    backup_schedule: str = "0 2 * * *"
    backup_retention_days: int = 30
    backup_path: str = "/backups"

    # ---------------------------------------------------------------
    # Validadores / propriedades derivadas
    # ---------------------------------------------------------------
    @field_validator("app_secret_key", "jwt_secret_key")
    @classmethod
    def _reject_placeholder(cls, v: str) -> str:
        if "GERAR" in v.upper() or "ALTERAR" in v.upper():
            raise ValueError(
                "chave contém valor de placeholder — gere uma chave real com "
                "`openssl rand -hex 48`"
            )
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins_list(self) -> list[str]:
        return _split_csv(self.cors_allowed_origins) or [self.frontend_url]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def privileged_groups_list(self) -> list[str]:
        return _split_csv(self.privileged_groups)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def critical_users_list(self) -> list[str]:
        return [u.lower() for u in _split_csv(self.critical_users)]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mfa_required_roles_list(self) -> list[str]:
        return [r.strip().lower() for r in _split_csv(self.mfa_required_roles)]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def role_group_map(self) -> dict[str, str]:
        """Grupo AD -> role da aplicação (maior privilégio vence na resolução)."""
        return {
            self.auth_group_admins.lower(): "administrator",
            self.auth_group_security.lower(): "security_analyst",
            self.auth_group_helpdesk.lower(): "helpdesk",
            self.auth_group_viewers.lower(): "viewer",
        }

    def event_id_set(self, csv_value: str) -> set[int]:
        return {int(x) for x in _split_csv(csv_value) if x.isdigit()}


# Variáveis obrigatórias sem as quais a aplicação NÃO deve subir.
REQUIRED_KEYS: list[str] = [
    "APP_SECRET_KEY",
    "JWT_SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
]


def validate_required_settings() -> Settings:
    """Instancia Settings e falha de forma clara se algo obrigatório faltar.

    Chamado no startup do backend (lifespan). Levanta RuntimeError com a
    lista exata de variáveis ausentes/inválidas.
    """
    import os

    missing = [k for k in REQUIRED_KEYS if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            "Configuração incompleta. As seguintes variáveis de ambiente "
            "OBRIGATÓRIAS estão ausentes: " + ", ".join(missing) + ". "
            "Copie .env.example para .env e preencha os valores."
        )
    try:
        settings = Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        raise RuntimeError(
            f"Configuração inválida no .env: {problems}"
        ) from exc

    if settings.ad_enabled and settings.auth_provider == "ldap":
        ldap_required = {
            "AD_LDAP_URI": settings.ad_ldap_uri,
            "AD_BIND_USERNAME": settings.ad_bind_username,
            "AD_BIND_PASSWORD": settings.ad_bind_password,
            "AD_BASE_DN": settings.ad_base_dn,
        }
        ldap_missing = [k for k, v in ldap_required.items() if not v]
        if ldap_missing:
            raise RuntimeError(
                "AD/LDAP habilitado mas faltam variáveis: "
                + ", ".join(ldap_missing)
            )
    return settings


@lru_cache
def get_settings() -> Settings:
    return validate_required_settings()
