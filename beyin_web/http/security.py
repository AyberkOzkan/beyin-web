from __future__ import annotations

import hmac
from collections.abc import Mapping, Sequence
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


def valid_write(headers: Mapping[str, Sequence[str]], port: int) -> bool:
    """A write must come from this page's own script, not from a form or another site.

    Browsers attach Origin to every POST; a form cannot send JSON or a custom header, and
    another origin's script needs a preflight for both, which this server never grants.
    """
    origins = headers.get("Origin", ())
    types = headers.get("Content-Type", ())
    return (
        len(origins) == 1 and origins[0] in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
        and len(types) == 1 and types[0].split(";", 1)[0].strip().lower() == "application/json"
        and list(headers.get("X-Beyin-Web", ())) == ["1"]
    )


def valid_token(candidate: str, token: str) -> bool:
    return bool(token) and hmac.compare_digest(
        candidate.encode("utf-8"), token.encode("utf-8"),
    )


def authenticated(cookies: Sequence[str], token: str, port: int) -> bool:
    if len(cookies) != 1:
        return False
    jar: SimpleCookie[str] = SimpleCookie()
    try:
        jar.load(cookies[0])
    except CookieError:
        return False
    session = jar.get(f"bw_session_{port}")
    return session is not None and valid_token(session.value, token)


LEGACY_COOKIE_CLEAR = "bw_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"


def session_cookie(session: str, port: int) -> str:
    return f"bw_session_{port}={session}; HttpOnly; SameSite=Strict; Path=/"
