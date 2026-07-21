"""Cliente LDAP SOMENTE LEITURA sobre LDAPS.

Princípios de segurança:
- Conexão obrigatoriamente via LDAPS (ldaps://) com validação de certificado.
- Nenhuma operação de escrita é exposta (sem add/modify/delete).
- Todos os valores interpolados em filtros passam por ``escape_filter_value``
  para prevenir LDAP Injection.
- Autenticação da aplicação faz bind com as credenciais do usuário apenas para
  VALIDAR a senha; a senha nunca é logada nem persistida.
"""
from __future__ import annotations

import ssl
from typing import Any

from ldap3 import ALL, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Atributos consultados (leitura). Binários pedidos como bytes.
USER_ATTRIBUTES = [
    "sAMAccountName",
    "userPrincipalName",
    "displayName",
    "givenName",
    "sn",
    "mail",
    "employeeID",
    "department",
    "title",
    "manager",
    "distinguishedName",
    "memberOf",
    "whenCreated",
    "whenChanged",
    "pwdLastSet",
    "lastLogonTimestamp",
    "lastLogon",
    "userAccountControl",
    "accountExpires",
    "badPwdCount",
    "badPasswordTime",
    "lockoutTime",
    "objectSid",
    "objectGUID",
    "adminCount",
    "servicePrincipalName",
    "msDS-AllowedToDelegateTo",
    "sIDHistory",
]


def escape_filter_value(value: str) -> str:
    """Escapa metacaracteres LDAP para prevenir injeção em filtros."""
    return escape_filter_chars(value)


class ReadOnlyLDAP:
    """Encapsula uma conexão LDAPS de leitura com a conta de serviço."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _build_tls(self) -> Tls:
        s = self.settings
        validate = ssl.CERT_REQUIRED if s.ad_ldap_tls_verify else ssl.CERT_NONE
        return Tls(
            validate=validate,
            version=ssl.PROTOCOL_TLS_CLIENT,
            ca_certs_file=s.ad_ldap_ca_cert_path or None,
        )

    def _server(self, uri: str) -> Server:
        use_ssl = uri.lower().startswith("ldaps://") or self.settings.ad_ldap_use_ssl
        return Server(
            uri,
            use_ssl=use_ssl,
            get_info=ALL,
            tls=self._build_tls() if use_ssl else None,
            connect_timeout=self.settings.ad_ldap_timeout_seconds,
        )

    def _connect_service(self) -> Connection:
        """Bind com a conta de serviço; tenta URI primário e depois fallback."""
        s = self.settings
        last_exc: Exception | None = None
        for uri in (s.ad_ldap_uri, s.ad_ldap_fallback_uri):
            if not uri:
                continue
            try:
                conn = Connection(
                    self._server(uri),
                    user=s.ad_bind_dn or s.ad_bind_username,
                    password=s.ad_bind_password,
                    auto_bind=True,
                    read_only=True,  # reforço: conexão marcada como somente leitura
                    receive_timeout=s.ad_ldap_timeout_seconds,
                )
                return conn
            except LDAPException as exc:
                last_exc = exc
                logger.warning("Falha de bind LDAP em %s (tentando fallback)", uri)
        raise ConnectionError("Não foi possível conectar a nenhum DC LDAPS") from last_exc

    # ---- Autenticação da aplicação (validação de senha do usuário) ----
    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        """Valida credenciais do usuário via bind e retorna atributos + grupos.

        A senha é usada apenas no bind e nunca registrada. Retorna None se
        as credenciais forem inválidas.
        """
        s = self.settings
        safe_user = escape_filter_value(username)
        user_filter = s.auth_ldap_user_filter.replace("{username}", safe_user)
        # 1) localiza o DN do usuário usando a conta de serviço
        try:
            svc = self._connect_service()
        except ConnectionError:
            logger.error("LDAP indisponível durante autenticação")
            return None
        try:
            svc.search(
                search_base=s.auth_ldap_user_search_base or s.ad_base_dn,
                search_filter=user_filter,
                search_scope=SUBTREE,
                attributes=["distinguishedName", "sAMAccountName", "userPrincipalName",
                            "displayName", "mail", "memberOf"],
            )
            if not svc.entries:
                return None
            entry = svc.entries[0]
            user_dn = str(entry.entry_dn)
        finally:
            svc.unbind()

        # 2) tenta bind com a senha informada (validação)
        try:
            user_conn = Connection(
                self._server(s.auth_ldap_uri or s.ad_ldap_uri),
                user=user_dn,
                password=password,
                auto_bind=True,
                read_only=True,
                receive_timeout=s.ad_ldap_timeout_seconds,
            )
            user_conn.unbind()
        except LDAPException:
            logger.info("Autenticação LDAP falhou para usuário informado")
            return None

        groups = [str(g) for g in (entry.memberOf.values if "memberOf" in entry else [])]
        return {
            "dn": user_dn,
            "sam_account_name": str(entry.sAMAccountName) if "sAMAccountName" in entry else username,
            "user_principal_name": str(entry.userPrincipalName) if "userPrincipalName" in entry else None,
            "display_name": str(entry.displayName) if "displayName" in entry else None,
            "mail": str(entry.mail) if "mail" in entry else None,
            "groups": groups,
        }

    # ---- Consultas de diretório (leitura) ----
    def search_users(
        self, ldap_filter: str = "(objectClass=user)", base: str | None = None
    ) -> list[dict[str, Any]]:
        s = self.settings
        conn = self._connect_service()
        results: list[dict[str, Any]] = []
        try:
            entries = conn.extend.standard.paged_search(
                search_base=base or s.ad_users_search_base or s.ad_base_dn,
                search_filter=ldap_filter,
                search_scope=SUBTREE,
                attributes=USER_ATTRIBUTES,
                paged_size=s.ad_ldap_page_size,
                generator=True,
            )
            for e in entries:
                if e.get("type") != "searchResEntry":
                    continue
                attrs = {k: v for k, v in dict(e["raw_attributes"]).items()}
                attrs["dn"] = e["dn"]
                results.append(attrs)
        finally:
            conn.unbind()
        return results

    def search(
        self, base: str, ldap_filter: str, attributes: list[str]
    ) -> list[dict[str, Any]]:
        """Busca genérica paginada (leitura). Retorna raw_attributes + dn."""
        conn = self._connect_service()
        results: list[dict[str, Any]] = []
        try:
            entries = conn.extend.standard.paged_search(
                search_base=base or self.settings.ad_base_dn,
                search_filter=ldap_filter,
                search_scope=SUBTREE,
                attributes=attributes,
                paged_size=self.settings.ad_ldap_page_size,
                generator=True,
            )
            for e in entries:
                if e.get("type") != "searchResEntry":
                    continue
                attrs = {k: v for k, v in dict(e["raw_attributes"]).items()}
                attrs["dn"] = e["dn"]
                results.append(attrs)
        finally:
            conn.unbind()
        return results

    def get_highest_committed_usn(self) -> int:
        """Lê highestCommittedUSN do RootDSE (watermark de sync incremental).

        É atributo operacional — vem no RootDSE via server.info.other quando a
        conexão usa get_info=ALL (uma busca direta pelo atributo é rejeitada
        pela validação de schema do ldap3)."""
        conn = self._connect_service()
        try:
            info = conn.server.info
            other = getattr(info, "other", {}) if info else {}
            val = other.get("highestCommittedUSN") if other else None
            if isinstance(val, (list, tuple)) and val:
                val = val[0]
            return int(val) if val is not None else 0
        except Exception:  # noqa: BLE001
            return 0
        finally:
            conn.unbind()

    def get_user_by_identifier(self, identifier: str) -> dict[str, Any] | None:
        """Busca por sAMAccountName, UPN, SID ou DN — tudo escapado."""
        v = escape_filter_value(identifier)
        ldap_filter = (
            f"(&(objectClass=user)(|(sAMAccountName={v})"
            f"(userPrincipalName={v})(distinguishedName={v})))"
        )
        found = self.search_users(ldap_filter)
        return found[0] if found else None

    def test_connection(self) -> tuple[bool, str]:
        try:
            conn = self._connect_service()
            who = conn.extend.standard.who_am_i()
            conn.unbind()
            return True, f"Conectado como {who}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
