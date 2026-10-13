from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer
from typing import cast
from urllib.parse import parse_qs, unquote, urlsplit

from beyin_web.config import Settings
from beyin_web.http.security import (
    SECURITY_HEADERS, authenticated, session_cookie, valid_host, valid_token, valid_write,
)
from beyin_web.runtime.beyin_cli import BeyinRuntime
from beyin_web.vault.scan import VaultSource


CONTENT_TYPES: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
}
DRAWING = re.compile(r"(hero-palace|sidebar-tree|heading-mountains|card-window)(?:-[a-z0-9]+)*\.(?:png|svg|webp)")
APIHandler = Callable[["RequestHandler", re.Match[str]], Mapping[str, object] | None]
WriteHandler = Callable[["RequestHandler", re.Match[str], Mapping[str, object]], None]
MAX_WRITE_BODY = 16 * 1024


class BeyinHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"

    def __init__(
        self, settings: Settings, source: VaultSource, runtime: BeyinRuntime,
    ) -> None:
        if settings.token_enabled and not settings.token:
            raise ValueError("missing_token")
        self.settings = settings
        self.source = source
        self.runtime = runtime
        # Every slot may hold several drawings (hero-palace.png, hero-palace-02.svg, ...); the page shows one at random.
        self.drawings: dict[str, list[str]] = {}
        static_root = settings.static_dir.resolve()
        try:
            for path in sorted((static_root / "img").iterdir(), key=lambda item: item.name):
                match = DRAWING.fullmatch(path.name)
                if match is not None and path.is_file() and path.resolve().is_relative_to(static_root):
                    self.drawings.setdefault(match.group(1), []).append(f"/static/img/{path.name}")
        except OSError:
            pass
        self.routes: list[tuple[re.Pattern[str], APIHandler]] = []
        self.write_routes: list[tuple[re.Pattern[str], WriteHandler]] = []
        # Commands to the server itself; they write nothing to the vault, so read-only mode keeps them.
        self.control_patterns: set[str] = set()
        self.activity = threading.Condition()
        self.last_request = time.monotonic()
        super().__init__(("127.0.0.1", settings.port), RequestHandler)
        from beyin_web.http.api import register_api
        self.api = register_api(self)
        self.control_patterns.add(r"/api/v1/shutdown")
        self.register_write(r"/api/v1/shutdown", _stop)

    def server_bind(self) -> None:
        # HTTPServer's default bind performs an unnecessary reverse DNS lookup.
        TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]

    def register(self, pattern: str, handler: APIHandler) -> None:
        """Register a full-path regex and a handler returning a JSON mapping."""
        self.routes.append((re.compile(pattern), handler))

    def register_write(self, pattern: str, handler: WriteHandler) -> None:
        """Register a full-path regex for POST; every other path keeps refusing the method."""
        self.write_routes.append((re.compile(pattern), handler))

    def note_request(self) -> None:
        with self.activity:
            self.last_request = time.monotonic()
            self.activity.notify_all()

    def handle_error(self, request: object, client_address: object) -> None:
        print("internal_error", file=sys.stderr)


class RequestHandler(BaseHTTPRequestHandler):
    _body_read = False

    @property
    def application(self) -> BeyinHTTPServer:
        return cast(BeyinHTTPServer, self.server)

    def log_message(self, format: str, *args: object) -> None:
        pass

    def log_error(self, format: str, *args: object) -> None:
        # Parser diagnostics can contain the request line and its secret.
        print("http_error", file=sys.stderr)

    def end_headers(self) -> None:
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_error(
        self, code: int, message: str | None = None, explain: str | None = None,
    ) -> None:
        if self.request_version == "HTTP/0.9":
            self.request_version = "HTTP/1.0"
        self._drain()
        error_code = {
            400: "bad_request", 401: "unauthorized", 403: "forbidden_host",
            404: "not_found", 405: "method_not_allowed", 500: "internal_error",
        }.get(code, "bad_request")
        print(f"http_error: {code}", file=sys.stderr)
        self.send_json(
            {"error": {"code": error_code, "message": error_code}}, code,
            {"Allow": "GET, HEAD"} if code == 405 else None,
        )

    def send_json(
        self, data: Mapping[str, object], status: int = 200,
        headers: Mapping[str, str] | None = None,
        *, etag: str | None = None,
    ) -> None:
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        response_headers = dict(headers or {})
        if status == 200 and etag is not None:
            response_headers["ETag"] = etag
            validators = self.headers.get("If-None-Match", "").split(",")
            if any(value.strip().removeprefix("W/") in {etag, "*"} for value in validators):
                self.send_body(304, b"", headers=response_headers)
                return
        self.send_body(status, body, "application/json; charset=utf-8", response_headers)

    def send_body(
        self, status: int, body: bytes, content_type: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        if content_type is not None:
            self.send_header("Content-Type", content_type)
        if status != 304:
            self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD" and status != 304:
            self.wfile.write(body)

    def do_GET(self) -> None:
        self._handle()

    def do_HEAD(self) -> None:
        self._handle()

    def __getattr__(self, name: str) -> Callable[[], None]:
        if name.startswith("do_"):
            return self._method_not_allowed
        raise AttributeError(name)

    def _method_not_allowed(self) -> None:
        self._handle()

    def _handle(self) -> None:
        self.application.note_request()
        try:
            self._dispatch()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # The browser went away mid-response (reload, navigation); there is nobody to answer
            # and nothing the user can act on, so the terminal stays quiet.
            pass
        except Exception:
            self.send_error(500)

    def _dispatch(self) -> None:
        application = self.application
        port = application.server_address[1]
        if not valid_host(self.headers.get_all("Host", []), port):
            self.send_error(403)
            return
        try:
            target = urlsplit(self.path)
            path = unquote(target.path, encoding="utf-8", errors="strict")
        except (ValueError, UnicodeError):
            self.send_error(405 if self.command not in {"GET", "HEAD"} else 400)
            return
        write = None
        if self.command == "POST":
            write = next(((handler, match) for pattern, handler in application.write_routes
                          if (match := pattern.fullmatch(path)) is not None), None)
        if self.command not in {"GET", "HEAD"} and write is None:
            self.send_error(405)
            return
        settings = application.settings
        if settings.token_enabled:
            query = parse_qs(target.query, keep_blank_values=True)
            tokens = query.get("t", [])
            if write is None and path == "/" and len(tokens) == 1 and valid_token(tokens[0], settings.token):
                self.send_body(302, b"", headers={
                    "Location": "/", "Set-Cookie": session_cookie(settings.token),
                })
                return
            if not authenticated(self.headers.get_all("Cookie", []), settings.token):
                if path.startswith(("/api/", "/static/")) or path in {"/api", "/static"}:
                    self.send_error(401)
                else:
                    self._serve_file("login.html", 401)
                return
        if write is not None:
            self._write(*write, port)
            return
        if path.startswith("/api/") or path == "/api":
            for pattern, handler in application.routes:
                match = pattern.fullmatch(path)
                if match is not None:
                    data = handler(self, match)
                    if data is not None:
                        self.send_json(data)
                    return
            self.send_error(404)
        elif path.startswith("/static/"):
            self._serve_file(path[len("/static/"):])
        else:
            self._serve_file("index.html")

    def _drain(self) -> None:
        """Take a small unread request body off the socket before refusing the request.

        Closing a connection with unread data makes some systems reset it, and the client then
        sees a broken connection instead of the 401, 403 or 405 it was sent.
        """
        headers = getattr(self, "headers", None)
        length = headers.get("Content-Length", "") if headers is not None else ""
        if not self._body_read and re.fullmatch(r"[0-9]{1,9}", length) and 0 < int(length) <= MAX_WRITE_BODY:
            self._read_body(int(length))

    def _read_body(self, length: int) -> bytes:
        self._body_read = True
        # A client that announces a body and never sends it must not hold this thread for good.
        self.connection.settimeout(5)
        try:
            return self.rfile.read(length)
        except OSError:
            return b""
        finally:
            self.connection.settimeout(None)

    def _refuse(self, status: int, code: str) -> None:
        self.send_json({"error": {"code": code, "message": code}}, status)

    def _write(self, handler: WriteHandler, match: re.Match[str], port: int) -> None:
        length = self.headers.get("Content-Length", "")
        if self.headers.get("Transfer-Encoding") or not re.fullmatch(r"[0-9]{1,9}", length):
            self._refuse(400, "bad_request")
            return
        # Read the body before any refusal, so the client receives the answer instead of a reset.
        raw = self._read_body(min(int(length), MAX_WRITE_BODY + 1))
        if int(length) > MAX_WRITE_BODY:
            self._refuse(413, "payload_too_large")
            return
        if len(raw) != int(length):
            self._refuse(400, "bad_request")
            return
        if self.application.settings.read_only and match.re.pattern not in self.application.control_patterns:
            self._refuse(403, "read_only")
            return
        if not valid_write({name: self.headers.get_all(name, [])
                            for name in ("Origin", "Content-Type", "X-Beyin-Web")}, port):
            self._refuse(403, "forbidden_origin")
            return
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError):
            body = None
        if not isinstance(body, dict):
            self._refuse(400, "bad_request")
            return
        handler(self, match, body)

    def _serve_file(self, relative: str, status: int = 200) -> None:
        root = self.application.settings.static_dir.resolve()
        try:
            candidate = root / relative
            content_type = CONTENT_TYPES.get(candidate.suffix.lower())
            path = candidate.resolve()
            if not path.is_relative_to(root) or not path.is_file():
                self.send_error(404)
                return
            if content_type is None or path.suffix.lower() not in CONTENT_TYPES:
                self.send_error(404)
                return
            body = path.read_bytes()
        except (OSError, ValueError, RuntimeError):
            self.send_error(404)
            return
        self.send_body(status, body, content_type)


def _stop(request: RequestHandler, match: re.Match[str], body: dict[str, object]) -> None:
    if body:
        request._refuse(400, "bad_request")
        return
    request.send_json({"stopping": True})
    # shutdown() waits for the serving loop, which is waiting for this very request to return.
    threading.Thread(target=request.application.shutdown, daemon=True).start()


def create_server(
    settings: Settings, source: VaultSource, runtime: BeyinRuntime,
) -> ThreadingHTTPServer:
    return BeyinHTTPServer(settings, source, runtime)
