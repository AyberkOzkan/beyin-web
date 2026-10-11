from __future__ import annotations

import hmac
from collections.abc import Sequence
from http.cookies import CookieError, SimpleCookie


SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
}


def valid_host(hosts: Sequence[str], port: int) -> bool:
    return len(hosts) == 1 and hosts[0] in {
        f"127.0.0.1:{port}", f"localhost:{port}",
    }


def valid_token(candidate: str, token: str) -> bool:
    return bool(token) and hmac.compare_digest(
        candidate.encode("utf-8"), token.encode("utf-8"),
    )


def authenticated(cookies: Sequence[str], token: str) -> bool:
    if len(cookies) != 1:
        return False
    jar: SimpleCookie[str] = SimpleCookie()
    try:
        jar.load(cookies[0])
    except CookieError:
        return False
    session = jar.get("bw_session")
    return session is not None and valid_token(session.value, token)


def session_cookie(token: str) -> str:
    return (
        f"bw_session={token}; HttpOnly; SameSite=Strict; Path=/; "
        "Max-Age=2592000"
    )
