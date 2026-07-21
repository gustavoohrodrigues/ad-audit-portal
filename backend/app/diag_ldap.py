"""Diagnóstico de conectividade/bind LDAP com o AD.

Uso (no servidor):
    docker compose exec backend python -m app.diag_ldap

Mostra: config efetiva, alcance de socket, bind direto com o erro REAL e o
resultado do cliente da aplicação. Somente leitura; não altera o AD.
"""
from __future__ import annotations

import socket
import ssl

from app.config import get_settings


def main() -> None:
    s = get_settings()
    raw = s.ad_ldap_uri or ""
    hostport = raw.split("://", 1)[-1]
    host = hostport.split(":")[0]
    try:
        port = int(hostport.split(":")[1])
    except (IndexError, ValueError):
        port = 636 if raw.lower().startswith("ldaps://") else 389

    print("=" * 60)
    print(f"URI            = {raw}")
    print(f"bind user      = {s.ad_bind_username}")
    print(f"bind pwd set   = {bool(s.ad_bind_password) and s.ad_bind_password != 'ALTERAR_PARA_SENHA_FORTE'}")
    print(f"use_ssl        = {s.ad_ldap_use_ssl} | tls_verify = {s.ad_ldap_tls_verify}")
    print(f"base_dn        = {s.ad_base_dn}")
    print(f"host:port      = {host}:{port}")
    print("=" * 60)

    # 1) socket
    try:
        socket.create_connection((host, port), timeout=6).close()
        print(f"[1] socket {host}:{port} -> ALCANCAVEL")
    except Exception as e:  # noqa: BLE001
        print(f"[1] socket {host}:{port} -> FALHOU: {type(e).__name__}: {e}")

    # 2) bind direto (mostra o erro exato)
    try:
        from ldap3 import Connection, Server, Tls

        use_ssl = raw.lower().startswith("ldaps://") or s.ad_ldap_use_ssl
        tls = Tls(validate=ssl.CERT_NONE) if use_ssl else None
        srv = Server(host, port=port, use_ssl=use_ssl, tls=tls, connect_timeout=6)
        c = Connection(
            srv, user=s.ad_bind_username, password=s.ad_bind_password,
            auto_bind=True, receive_timeout=6,
        )
        print(f"[2] bind -> OK: {c.extend.standard.who_am_i()}")
        c.unbind()
    except Exception as e:  # noqa: BLE001
        print(f"[2] bind -> FALHOU: {type(e).__name__}: {str(e)[:300]}")

    # 3) cliente da aplicação
    try:
        from app.ldap.client import ReadOnlyLDAP

        ok, msg = ReadOnlyLDAP().test_connection()
        print(f"[3] test_connection -> ok={ok} | {msg}")
    except Exception as e:  # noqa: BLE001
        print(f"[3] test_connection -> ERRO: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
