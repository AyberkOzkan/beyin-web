from __future__ import annotations

import contextlib
import http.client
import io
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beyin_web.config import LANGUAGES, config_directory, load_settings, load_token, read_config
from beyin_web.http.security import SECURITY_HEADERS
from tests.support import make_vault
from tests.test_server import ServerCase


class SecurityTests(ServerCase):
    token_enabled = True

    def test_wrong_hosts_and_host_before_token(self) -> None:
        for host in ("evil.example", f"evil.example:{self.server.server_port}", "localhost", "127.0.0.1:0", "[::1]:7373"):
            with self.subTest(host=host):
                status, headers, body = self.request("/?t=test_session_secret", headers={"Host": host})
                self.assertEqual(status, 403)
                self.assertNotIn("Set-Cookie", headers)
                self.assertEqual(json.loads(body)["error"]["code"], "forbidden_host")
        status, _, _ = self.request("/", "POST", {"Host": "evil.example"})
        self.assertEqual(status, 403)

    def test_missing_and_duplicate_host(self) -> None:
        for hosts in ([], [f"localhost:{self.server.server_port}", "evil.example"]):
            with self.subTest(hosts=hosts):
                connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
                try:
                    connection.putrequest("GET", "/api/v1/pulse", skip_host=True)
                    for host in hosts:
                        connection.putheader("Host", host)
                    connection.endheaders()
                    response = connection.getresponse()
                    self.assertEqual(response.status, 403)
                    for name, value in SECURITY_HEADERS.items():
                        self.assertEqual(response.getheader(name), value)
                    self.assertEqual(json.loads(response.read())["error"]["code"], "forbidden_host")
                finally:
                    connection.close()

    def test_no_cookie_api_and_static_are_unauthorized(self) -> None:
        for path in ("/api/v1/pulse", "/api/v1/missing", "/static/index.html", "/static/login.html"):
            with self.subTest(path=path):
                status, headers, body = self.request(path)
                self.assertEqual(status, 401)
                self.assertEqual(json.loads(body)["error"]["code"], "unauthorized")
                self.assertNotIn("Set-Cookie", headers)

    def test_login_page_is_standalone_and_head_is_empty(self) -> None:
        for path in ("/", "/unknown/page"):
            with self.subTest(path=path):
                status, headers, body = self.request(path)
                self.assertEqual(status, 401)
                self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
                self.assertEqual(body, (self.static_dir / "login.html").read_bytes())
                text = body.decode("utf-8")
                self.assertIn("terminalde", text)
                for forbidden in ("<script", "<style", "style=", "src=", "href="):
                    self.assertNotIn(forbidden, text)
                head_status, _, head_body = self.request(path, "HEAD")
                self.assertEqual((head_status, head_body), (401, b""))

    def test_incorrect_tokens_never_set_cookie(self) -> None:
        for query in ("t=wrong", "t=", "t=%C3%BC", "t=test_session_secret&t=wrong"):
            with self.subTest(query=query):
                status, headers, _ = self.request(f"/?{query}")
                self.assertEqual(status, 401)
                self.assertNotIn("Set-Cookie", headers)
        status, headers, _ = self.request("/api/v1/pulse?t=test_session_secret")
        self.assertEqual(status, 401)
        self.assertNotIn("Set-Cookie", headers)

    def test_correct_token_redirect_and_cookie_access(self) -> None:
        for method in ("GET", "HEAD"):
            with self.subTest(method=method):
                status, headers, body = self.request("/?t=test_session_secret", method)
                self.assertEqual((status, body), (302, b""))
                self.assertEqual(headers["Location"], "/")
                self.assertEqual(headers["Set-Cookie"], (
                    "bw_session=test_session_secret; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000"
                ))
        cookie = {"Cookie": "bw_session=test_session_secret"}
        for path in ("/", "/static/index.html", "/api/v1/pulse"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path, headers=cookie)[0], 200)
        self.assertEqual(self.request("/api/v1/pulse", headers={**cookie, "Host": f"localhost:{self.server.server_port}"})[0], 200)

    def test_invalid_cookies_are_unauthorized(self) -> None:
        for cookie in ("bw_session=wrong", "other=test_session_secret", "bw_session=", "bw_session=wrong; broken"):
            with self.subTest(cookie=cookie):
                status, headers, body = self.request("/api/v1/pulse", headers={"Cookie": cookie})
                self.assertEqual(status, 401)
                self.assertEqual(json.loads(body)["error"]["code"], "unauthorized")
                self.assertNotIn("Set-Cookie", headers)

    def test_method_rejection_does_not_create_session(self) -> None:
        for method in ("POST", "PUT", "DELETE"):
            with self.subTest(method=method):
                status, headers, body = self.request("/?t=test_session_secret", method)
                self.assertEqual(status, 405)
                self.assertNotIn("Set-Cookie", headers)
                self.assertEqual(json.loads(body)["error"]["code"], "method_not_allowed")

    def test_no_token_still_checks_host(self) -> None:
        self.server.settings = type(self.settings)(self.vault, token_enabled=False, static_dir=self.static_dir)
        self.assertEqual(self.request("/api/v1/pulse")[0], 200)
        status, _, body = self.request("/api/v1/pulse", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"]["code"], "forbidden_host")

    def test_error_logs_redact_request_and_secret(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            self.request("/api/v1/pulse?t=private-secret", headers={"Host": "evil.example"})
        self.assertEqual(output.getvalue(), "http_error: 403\n")

    def test_client_disconnect_is_not_reported(self) -> None:
        from beyin_web.http.server import RequestHandler
        output = io.StringIO()
        with patch.object(RequestHandler, "_dispatch", side_effect=ConnectionResetError), \
                contextlib.redirect_stderr(output):
            with self.assertRaises((http.client.HTTPException, OSError)):
                self.request("/api/v1/pulse")
        self.assertEqual(output.getvalue(), "")

    def test_parser_errors_have_security_headers_and_no_request_echo(self) -> None:
        output = io.StringIO()
        with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=5) as connection:
            with contextlib.redirect_stderr(output):
                connection.sendall(b"GET /?t=private-secret HTTP/bad\r\n\r\n")
                response = http.client.HTTPResponse(connection)
                response.begin()
                body = response.read()
            self.assertEqual(response.status, 400)
            for name, value in SECURITY_HEADERS.items():
                self.assertEqual(response.getheader(name), value)
            self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))
            self.assertNotIn("private-secret", body.decode("utf-8") + output.getvalue())


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = make_vault(self.root)

    def test_platform_config_directories(self) -> None:
        self.assertEqual(config_directory({"APPDATA": str(self.root), "XDG_CONFIG_HOME": "ignored"}, "win32"), self.root / "beyin-web")
        self.assertEqual(config_directory({"XDG_CONFIG_HOME": str(self.root)}, "linux"), self.root / "beyin-web")
        with patch("beyin_web.config.Path.home", return_value=self.root):
            for platform in ("linux", "darwin", "win32"):
                self.assertEqual(config_directory({}, platform), self.root / ".config" / "beyin-web")

    def test_token_persists_across_starts(self) -> None:
        directory = self.root / "config"
        first = load_settings(self.vault, directory)
        content = (directory / "token").read_text(encoding="utf-8")
        with patch("beyin_web.config.secrets.token_urlsafe") as generate:
            second = load_settings(self.vault, directory)
            generate.assert_not_called()
        self.assertEqual(first.token, second.token)
        self.assertEqual(content, (directory / "token").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(first.token), 43)
        if os.name != "nt":
            self.assertEqual((directory / "token").stat().st_mode & 0o777, 0o600)

    def test_token_bom_crlf_and_invalid_file(self) -> None:
        directory = self.root / "config"
        directory.mkdir()
        path = directory / "token"
        path.write_text("\ufefftest_token\r\n", encoding="utf-8", newline="")
        self.assertEqual(load_token(directory), "test_token")
        for text in ("", "bad token", "bad\nvalue", "ü"):
            with self.subTest(text=text):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_token(directory)
                self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_config_values_and_cli_override(self) -> None:
        directory = self.root / "config"
        directory.mkdir()
        (directory / "config.json").write_text(
            '\ufeff{\r\n"vault": "unused", "port": 7474, "display_name": "Çınar"\r\n}', encoding="utf-8", newline="",
        )
        settings = load_settings(self.vault, directory, token_enabled=False)
        self.assertEqual((settings.port, settings.display_name), (7474, "Çınar"))
        self.assertEqual(load_settings(self.vault, directory, port=0, token_enabled=False).port, 0)
        self.assertFalse((directory / "token").exists())

    def test_invalid_optional_config(self) -> None:
        directory = self.root / "config"
        directory.mkdir()
        path = directory / "config.json"
        for content in ("{", "[]", "null", '{"port": true}', '{"port": -1}', '{"port": "7474", "display_name": 3}'):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                settings = load_settings(self.vault, directory, token_enabled=False)
                self.assertEqual(settings.port, 7373)
                self.assertEqual(settings.display_name, "")
        self.assertEqual(read_config(directory / "missing.json"), {})

    def test_language_comes_from_cli_then_config_then_default(self) -> None:
        directory = self.root / "config"
        directory.mkdir()
        path = directory / "config.json"
        self.assertEqual(load_settings(self.vault, directory, token_enabled=False).language, "tr")
        path.write_text('{"language": "en"}', encoding="utf-8")
        self.assertEqual(load_settings(self.vault, directory, token_enabled=False).language, "en")
        self.assertEqual(load_settings(self.vault, directory, token_enabled=False, language="tr").language, "tr")
        for content in ('{"language": "de"}', '{"language": "../en"}', '{"language": 3}', '{"language": ["en"]}'):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                self.assertEqual(load_settings(self.vault, directory, token_enabled=False).language, "tr")
                self.assertEqual(load_settings(self.vault, directory, token_enabled=False, language="en").language, "en")

    def test_every_language_has_messages_and_the_page_knows_it(self) -> None:
        static = Path(__file__).resolve().parents[1] / "beyin_web" / "static"
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertTrue((static / "i18n" / f"{language}.json").is_file())
        script = (static / "js" / "i18n.js").read_text(encoding="utf-8")
        self.assertIn("export const LANGUAGES = [" + ", ".join(f'"{language}"' for language in LANGUAGES) + "];", script)

    def test_config_cannot_write_inside_vault(self) -> None:
        with self.assertRaises(ValueError):
            load_settings(self.vault, self.vault / ".config")
        self.assertFalse((self.vault / ".config").exists())


if __name__ == "__main__":
    unittest.main()
