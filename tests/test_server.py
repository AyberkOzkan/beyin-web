from __future__ import annotations

import contextlib
import errno
import http.client
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import cast
from unittest.mock import Mock, patch

from beyin_web.__main__ import bind_server, main, open_address, parse_args, serve
from beyin_web.config import Settings
from beyin_web.http.security import SECURITY_HEADERS
from beyin_web.http.server import BeyinHTTPServer, RequestHandler, create_server
from beyin_web.runtime.beyin_cli import BeyinRuntime
from beyin_web.vault.scan import MarkdownSource
from tests.support import FIXTURES, make_vault


ROOT = Path(__file__).resolve().parents[1]


class ServerCase(unittest.TestCase):
    token_enabled = False

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = make_vault(self.root)
        self.static_dir = self.root / "static"
        shutil.copytree(ROOT / "beyin_web" / "static", self.static_dir)
        self.settings = Settings(
            vault=self.vault, port=0, token_enabled=self.token_enabled,
            token="test_session_secret", static_dir=self.static_dir,
        )
        self.source = MarkdownSource(self.vault, min_interval=0)
        self.runtime = BeyinRuntime(self.vault)
        self.server = cast(BeyinHTTPServer, create_server(self.settings, self.source, self.runtime))
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()

    def request(
        self, path: str, method: str = "GET", headers: Mapping[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, headers=dict(headers or {}))
            response = connection.getresponse()
            response_headers = dict(response.getheaders())
            body = response.read()
            for name, value in SECURITY_HEADERS.items():
                self.assertEqual(response_headers.get(name), value)
            self.assertNotIn("Access-Control-Allow-Origin", response_headers)
            self.assertEqual(response_headers.get("Cache-Control"), "no-store")
            return response.status, response_headers, body
        finally:
            connection.close()


class ServerTests(ServerCase):
    def test_loopback_binding_and_no_token(self) -> None:
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertGreater(self.server.server_port, 0)
        status, _, body = self.request("/api/v1/pulse")
        self.assertEqual(status, 200)
        self.assertIn("generation", json.loads(body))

    def test_pulse_and_conditional_requests(self) -> None:
        status, headers, body = self.request("/api/v1/pulse")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        snapshot = self.source.snapshot()
        self.assertEqual(set(payload), {"generation", "scanned_at", "records", "hidden_private", "beyin"})
        self.assertEqual(payload["generation"], snapshot.generation)
        self.assertEqual(payload["records"], len(snapshot.records))
        self.assertEqual(payload["hidden_private"], snapshot.hidden_private)
        self.assertEqual(payload["beyin"], {"available": False, "version": None, "up_to_date": None})
        self.assertNotIn("Gizli", body.decode("utf-8"))
        for validator in (headers["ETag"], f'W/{headers["ETag"]}', f'"other", {headers["ETag"]}', "*"):
            with self.subTest(validator=validator):
                status, second_headers, body = self.request("/api/v1/pulse", headers={"If-None-Match": validator})
                self.assertEqual(status, 304)
                self.assertEqual(body, b"")
                self.assertEqual(second_headers["ETag"], headers["ETag"])
        note = self.vault / "notes" / "added.md"
        note.write_text("# Added\n", encoding="utf-8")
        status, changed_headers, body = self.request("/api/v1/pulse", headers={"If-None-Match": headers["ETag"]})
        self.assertEqual(status, 200)
        self.assertNotEqual(changed_headers["ETag"], headers["ETag"])
        self.assertEqual(json.loads(body)["records"], payload["records"] + 1)

    def test_pulse_reuses_doctor_cache(self) -> None:
        log = self.root / "cli.jsonl"
        self.server.runtime = BeyinRuntime(self.vault, script=FIXTURES / "fake_beyin.py")
        with patch.dict(os.environ, {"FAKE_BEYIN_LOG": str(log), "FAKE_BEYIN_MODE": "ok"}):
            self.server.runtime.doctor()
            for _ in range(2):
                status, _, body = self.request("/api/v1/pulse")
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["beyin"], {
                    "available": True, "version": "0.1.0", "up_to_date": True,
                })
        self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ['["doctor"]'])

    def test_pulse_with_unreachable_beyin(self) -> None:
        self.server.runtime = BeyinRuntime(self.vault, script=FIXTURES / "fake_beyin.py")
        with patch.dict(os.environ, {"FAKE_BEYIN_MODE": "badjson"}):
            status, _, body = self.request("/api/v1/pulse")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["beyin"], {"available": True, "version": None, "up_to_date": None})

    def test_index_fallback_and_unknown_api(self) -> None:
        for path in ("/", "/unknown/page?query=secret", "/apiary"):
            with self.subTest(path=path):
                status, headers, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
                self.assertEqual(body, (self.static_dir / "index.html").read_bytes())
        for path in ("/api/v1/missing", "/api/v2/pulse", "/api/"):
            with self.subTest(path=path):
                status, headers, body = self.request(path)
                self.assertEqual(status, 404)
                self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
                self.assertEqual(json.loads(body)["error"]["code"], "not_found")

    def test_head_has_headers_and_no_body(self) -> None:
        for path in ("/", "/static/index.html", "/api/v1/pulse", "/api/v1/missing"):
            with self.subTest(path=path):
                get_status, get_headers, get_body = self.request(path)
                head_status, head_headers, body = self.request(path, "HEAD")
                self.assertEqual(head_status, get_status)
                self.assertEqual(body, b"")
                self.assertEqual(head_headers["Content-Length"], str(len(get_body)))
                self.assertEqual(head_headers["Content-Type"], get_headers["Content-Type"])
        _, headers, _ = self.request("/api/v1/pulse")
        status, _, body = self.request("/api/v1/pulse", "HEAD", {"If-None-Match": headers["ETag"]})
        self.assertEqual((status, body), (304, b""))

    def test_unsupported_methods(self) -> None:
        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS", "TRACE", "CONNECT", "CUSTOM"):
            with self.subTest(method=method):
                status, headers, body = self.request("/api/v1/pulse", method)
                self.assertEqual(status, 405)
                self.assertEqual(headers["Allow"], "GET, HEAD")
                self.assertEqual(json.loads(body)["error"]["code"], "method_not_allowed")

    def test_static_content_types_and_disallowed_extensions(self) -> None:
        content_types = {
            "html": "text/html; charset=utf-8", "css": "text/css; charset=utf-8",
            "js": "text/javascript; charset=utf-8", "json": "application/json; charset=utf-8",
            "svg": "image/svg+xml", "png": "image/png", "woff2": "font/woff2",
        }
        for extension, content_type in content_types.items():
            with self.subTest(extension=extension):
                asset = self.static_dir / f"asset.{extension}"
                asset.write_bytes(b"static-content")
                status, headers, body = self.request(f"/static/asset.{extension}")
                self.assertEqual((status, body), (200, b"static-content"))
                self.assertEqual(headers["Content-Type"], content_type)
        for name in ("secret.md", "unknown.txt", "extensionless"):
            (self.static_dir / name).write_text("secret-content", encoding="utf-8")
            status, _, body = self.request(f"/static/{name}")
            self.assertEqual(status, 404)
            self.assertNotIn(b"secret-content", body)
        self.assertEqual(self.request("/static/missing.js")[0], 404)

    def test_static_traversal(self) -> None:
        (self.root / "outside.html").write_text("outside-secret", encoding="utf-8")
        paths = (
            "/static/../../pyproject.toml", "/static/%2e%2e/%2e%2e/pyproject.toml",
            "/static/%2E%2E%2foutside.html", "/static/../outside.html",
            "/static/..%5coutside.html", "/static/%252e%252e/outside.html",
            "/static/%2foutside.html", "/static/%00.html",
        )
        for path in paths:
            with self.subTest(path=path):
                status, _, body = self.request(path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"outside-secret", body)

    def test_static_symlink_escape(self) -> None:
        outside = self.root / "outside.html"
        outside.write_text("outside-secret", encoding="utf-8")
        try:
            (self.static_dir / "escape.html").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symbolic links are unavailable on this platform")
        self.assertEqual(self.request("/static/escape.html")[0], 404)
        (self.static_dir / "hidden.md").symlink_to(self.static_dir / "index.html")
        self.assertEqual(self.request("/static/hidden.md")[0], 404)

    def test_invalid_url_encoding_is_bad_request(self) -> None:
        status, _, body = self.request("/static/%ff.html")
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"]["code"], "bad_request")

    def test_register_dispatch_and_exception_redaction(self) -> None:
        def registered(request: RequestHandler, match: re.Match[str]) -> Mapping[str, object]:
            return {"generation": request.application.source.snapshot().generation, "value": match["value"]}

        def failing(request: RequestHandler, match: re.Match[str]) -> Mapping[str, object]:
            raise RuntimeError(f"{self.vault}: sensitive-query-token")

        self.server.register(r"/api/v1/items/(?P<value>[^/]+)", registered)
        self.server.register(r"/api/v1/failing", failing)
        status, _, body = self.request("/api/v1/items/example")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["value"], "example")
        self.assertEqual(self.request("/api/v1/items/example/extra")[0], 404)
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            status, _, body = self.request("/api/v1/failing?t=sensitive-query-token")
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body)["error"]["code"], "internal_error")
        for secret in (str(self.vault), "sensitive-query-token", "/api/v1/failing", "Traceback"):
            self.assertNotIn(secret, body.decode("utf-8") + output.getvalue())

    def test_successful_requests_are_silent(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            self.request("/?t=secret-query")
            self.request("/api/v1/pulse")
        self.assertEqual(output.getvalue(), "")


class LaunchTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = make_vault(self.root)

    def test_startup_avoids_dns_lookups(self) -> None:
        with patch("socket.getfqdn", side_effect=AssertionError("unexpected DNS lookup")):
            server = create_server(
                Settings(self.vault, port=0, token_enabled=False),
                MarkdownSource(self.vault), BeyinRuntime(self.vault),
            )
        self.addCleanup(server.server_close)
        self.assertEqual(server.server_name, "127.0.0.1")

    def test_port_retry_limit_and_non_address_errors(self) -> None:
        settings = Settings(self.vault, port=7373, token_enabled=False)
        source = MarkdownSource(self.vault)
        runtime = BeyinRuntime(self.vault)
        expected = Mock()
        with patch("beyin_web.__main__.create_server", side_effect=[OSError(errno.EADDRINUSE, "busy"), expected]) as factory:
            self.assertIs(bind_server(settings, source, runtime), expected)
            self.assertEqual([call.args[0].port for call in factory.call_args_list], [7373, 7374])
        with patch("beyin_web.__main__.create_server", side_effect=OSError(errno.EADDRINUSE, "busy")) as factory:
            with self.assertRaises(OSError):
                bind_server(settings, source, runtime)
            self.assertEqual(factory.call_count, 21)
            self.assertEqual(factory.call_args.args[0].port, 7393)
        with patch("beyin_web.__main__.create_server", side_effect=OSError(errno.EACCES, "denied")) as factory:
            with self.assertRaises(OSError):
                bind_server(settings, source, runtime)
            self.assertEqual(factory.call_count, 1)

    def test_occupied_port_is_skipped(self) -> None:
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            server = bind_server(
                Settings(self.vault, port=port, token_enabled=False),
                MarkdownSource(self.vault), BeyinRuntime(self.vault),
            )
            self.addCleanup(server.server_close)
            self.assertGreater(server.server_port, port)
            self.assertLessEqual(server.server_port, port + 20)

    def test_browser_opening(self) -> None:
        address = "http://127.0.0.1:7373/?t=secret"
        with patch.dict(os.environ, {}, clear=True), patch("beyin_web.__main__.webbrowser.open") as browser:
            open_address(address)
            browser.assert_called_once_with(address)
        for executable in ("/usr/bin/wslview", None):
            with (
                self.subTest(executable=executable),
                patch.dict(os.environ, {"WSL_DISTRO_NAME": "test"}),
                patch("beyin_web.__main__.shutil.which", return_value=executable),
                patch("beyin_web.__main__.subprocess.Popen") as process,
            ):
                open_address(address)
                self.assertEqual(process.call_args.args[0], [executable or "explorer.exe", address])

    def test_main_config_and_companion_setup(self) -> None:
        config_dir = self.root / "config"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(json.dumps({"vault": str(self.vault), "port": 7474}), encoding="utf-8")
        runtime = Mock(available=True)
        runtime.doctor.return_value = {"companion_hygiene": {"directory": "custom-companion"}}
        server = Mock(server_address=("127.0.0.1", 7474))
        for arguments, expected_port in (([], 7474), (["--port", "0"], 0)):
            with (
                self.subTest(arguments=arguments),
                patch("beyin_web.__main__.config_directory", return_value=config_dir),
                patch.dict(os.environ, {}, clear=True),
                patch("beyin_web.__main__.BeyinRuntime", return_value=runtime),
                patch("beyin_web.__main__.MarkdownSource") as source,
                patch("beyin_web.__main__.bind_server", return_value=server) as bind,
                patch("beyin_web.__main__.serve") as serving,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(main(arguments), 0)
                source.assert_called_once_with(self.vault.resolve(), companion_dir="custom-companion")
                self.assertEqual(bind.call_args.args[0].port, expected_port)
                self.assertIn("/?t=", output.getvalue())
                serving.assert_called_once_with(server, None)

    def test_clean_ctrl_c_and_no_idle_thread_by_default(self) -> None:
        server = Mock()
        server.serve_forever.side_effect = KeyboardInterrupt
        with patch("beyin_web.__main__.threading.Thread") as thread:
            serve(server, None)
        server.server_close.assert_called_once()
        thread.assert_not_called()

    def test_idle_shutdown_and_request_reset(self) -> None:
        server = cast(BeyinHTTPServer, create_server(
            Settings(self.vault, port=0, token_enabled=False),
            MarkdownSource(self.vault), BeyinRuntime(self.vault),
        ))
        # A short test deadline exercises the same minutes-to-seconds conversion.
        runner = threading.Thread(target=serve, args=(server, 0.01))
        runner.start()
        try:
            for _ in range(3):
                time.sleep(0.25)
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    connection.request("GET", "/")
                    self.assertEqual(connection.getresponse().status, 200)
                finally:
                    connection.close()
                self.assertTrue(runner.is_alive())
            runner.join(timeout=5)
            self.assertFalse(runner.is_alive())
        finally:
            if runner.is_alive():
                server.shutdown()
                runner.join(timeout=5)
            server.server_close()

    def test_invalid_port_and_idle_values(self) -> None:
        for arguments in (["--port", "-1"], ["--port", "65536"], ["--idle-exit", "0"], ["--idle-exit", "-1"]):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    parse_args(arguments)
                self.assertEqual(caught.exception.code, 2)

    def test_cli_fixture_pulse(self) -> None:
        environment = os.environ.copy()
        environment.update({"APPDATA": str(self.root), "XDG_CONFIG_HOME": str(self.root), "PYTHONUTF8": "1"})
        process = subprocess.Popen(
            [sys.executable, "-m", "beyin_web", "--vault", "tests/fixtures/vault", "--no-token", "--port", "0"],
            cwd=ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
        )
        try:
            assert process.stdout is not None
            line = process.stdout.readline()
            match = re.search(r"http://127\.0\.0\.1:(\d+)/", line)
            self.assertIsNotNone(match, line)
            assert match is not None
            connection = http.client.HTTPConnection("127.0.0.1", int(match[1]), timeout=5)
            try:
                connection.request("GET", "/api/v1/pulse")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn("generation", json.loads(response.read()))
            finally:
                connection.close()
        finally:
            process.terminate()
            _, stderr = process.communicate(timeout=10)
        self.assertIn("yalın kip", stderr)
        self.assertFalse((self.root / "beyin-web" / "token").exists())


if __name__ == "__main__":
    unittest.main()
