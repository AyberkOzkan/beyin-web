from __future__ import annotations

import json
import os
import select
import socket
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from beyin_web.__main__ import find_running, serve
from beyin_web.config import load_settings
from beyin_web.domain.obsidian import obsidian_vault_uri
from beyin_web.http.server import BeyinHTTPServer
from beyin_web.running import read_running, remove_running, write_running
from beyin_web.runtime.beyin_cli import BeyinRuntime
from beyin_web.vault.scan import MarkdownSource
from tests.support import make_vault
from upstream import beyin_v3_web as launcher


class RunningTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = make_vault(self.root)
        self.config = self.root / "config"
        self.threads: dict[int, threading.Thread] = {}
        self.settings = load_settings(self.vault, self.config, port=0)

    def start(self, *, token_enabled: bool = True) -> BeyinHTTPServer:
        server = BeyinHTTPServer(replace(self.settings, token_enabled=token_enabled),
                                 MarkdownSource(self.vault), BeyinRuntime(self.vault, enabled=False))
        write_running(server)
        thread = threading.Thread(target=serve, args=(server, None))
        thread.start()
        self.threads[server.server_port] = thread

        def stop() -> None:
            if thread.is_alive():
                server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        self.addCleanup(stop)
        return server

    def lock(self, port_number: int, **changes: object) -> Path:
        directory = self.config / "running"
        directory.mkdir(exist_ok=True)
        path = directory / f"{port_number}.json"
        path.write_text(json.dumps({"schema": 1, "port": port_number, "pid": os.getpid(),
                                    "vault": str(self.vault.resolve()), "session": "temporary_session",
                                    **changes}), encoding="utf-8")
        return path

    def both(self, expected: int | None) -> None:
        self.assertEqual(find_running(self.settings), expected)
        self.assertEqual(launcher.find_running(self.vault, self.config), expected)

    def test_no_connection_to_a_listener_without_a_lock_even_in_port_range(self) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            self.settings = replace(self.settings, port=listener.getsockname()[1])
            self.both(None)
            self.assertEqual(select.select([listener], [], [], 0)[0], [])

    def test_live_server_and_no_token_server_are_found_even_with_port_zero(self) -> None:
        for enabled in (True, False):
            server = self.start(token_enabled=enabled)
            port = server.server_port
            path = self.config / "running" / f"{port}.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(value, {"schema": 1, "port": port, "pid": os.getpid(),
                                     "vault": str(self.vault.resolve()), "session": server.session if enabled else ""})
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.both(port)
            server.shutdown()
            self.threads[port].join(timeout=5)
            self.assertFalse(self.threads[port].is_alive())
            self.assertFalse(path.exists())

    def test_other_vault_is_rejected_without_connecting(self) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            path = self.lock(listener.getsockname()[1], vault=str(self.root / "other"))
            self.both(None)
            self.assertEqual(select.select([listener], [], [], 0)[0], [])
            self.assertTrue(path.exists())

    def test_stale_lock_is_left_in_place(self) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        path = self.lock(port)
        before = path.read_bytes()
        self.both(None)
        self.assertEqual(path.read_bytes(), before)

    def test_probe_never_sends_the_persistent_token(self) -> None:
        for finder in (lambda: find_running(self.settings),
                       lambda: launcher.find_running(self.vault, self.config)):
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen()
                listener.settimeout(5)
                port = listener.getsockname()[1]
                path = self.lock(port)
                received: list[bytes] = []

                def respond() -> None:
                    connection, _ = listener.accept()
                    with connection:
                        connection.settimeout(5)
                        request = b""
                        while b"\r\n\r\n" not in request:
                            request += connection.recv(4096)
                        received.append(request)
                        body = json.dumps({"obsidian_uri": obsidian_vault_uri(str(self.vault.resolve()))}).encode()
                        connection.sendall(b"HTTP/1.0 200 OK\r\nContent-Length: " + str(len(body)).encode()
                                           + b"\r\n\r\n" + body)

                thread = threading.Thread(target=respond)
                thread.start()
                try:
                    self.assertEqual(finder(), port)
                finally:
                    thread.join(timeout=5)
                self.assertFalse(thread.is_alive())
                self.assertNotIn(self.settings.token.encode(), received[0])
                self.assertIn(f"Cookie: bw_session_{port}=temporary_session\r\n".encode(), received[0])
                self.assertIn(b"GET /api/v1/pulse HTTP/1.1\r\n", received[0])
                path.unlink()

    def test_mismatching_pulse_and_wrong_session_are_not_reused_or_deleted(self) -> None:
        server = self.start()
        path = self.config / "running" / f"{server.server_port}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        with patch("beyin_web.http.api.obsidian_vault_uri", return_value="obsidian://wrong"):
            self.both(None)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), value)
        value["session"] = "other_session"
        path.write_text(json.dumps(value), encoding="utf-8")
        self.both(None)
        server.shutdown()
        self.threads[server.server_port].join(timeout=5)
        self.assertFalse(self.threads[server.server_port].is_alive())
        self.assertTrue(path.exists())
        remove_running(server)
        self.assertTrue(path.exists())

    def test_invalid_locks_are_never_probed(self) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            invalid = ({"schema": True}, {"schema": 2}, {"port": True}, {"port": str(port)},
                       {"port": 0}, {"pid": False}, {"pid": -1}, {"vault": 42}, {"vault": "relative"},
                       {"session": None}, {"session": "injected\r\nHeader: value"}, {"port": port % 65535 + 1})
            for changes in invalid:
                with self.subTest(changes=changes):
                    path = self.lock(port, **changes)
                    self.assertIsNone(read_running(path))
                    self.assertIsNone(launcher.read_running(path))
                    self.both(None)
            for text in ("{", "[]", "null", "{}", "\ufeff\xff"):
                path.write_text(text, encoding="utf-8")
                self.both(None)
            path.write_bytes(b"\xff\xfe")
            self.both(None)
            path.unlink()
            path.mkdir()
            self.both(None)
            path.rmdir()
            self.assertEqual(select.select([listener], [], [], 0)[0], [])

    def test_unreadable_lock_is_ignored(self) -> None:
        path = self.lock(12345)
        with patch.object(Path, "read_text", side_effect=PermissionError):
            self.assertIsNone(read_running(path))
            self.assertIsNone(launcher.read_running(path))
            self.both(None)
        self.assertTrue(path.exists())

    def test_symlink_lock_is_ignored(self) -> None:
        path = self.lock(12345)
        target = path.with_suffix(".txt")
        path.rename(target)
        try:
            path.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links unavailable")
        self.both(None)
        self.assertIsNone(read_running(path))
        self.assertIsNone(launcher.read_running(path))

    def test_lock_failures_do_not_stop_the_server_or_leave_temporary_files(self) -> None:
        server = self.start()
        path = self.config / "running" / f"{server.server_port}.json"
        before = path.read_bytes()
        with patch("beyin_web.running.os.replace", side_effect=OSError):
            write_running(server)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(path.parent.glob("*.tmp")), [])
        with patch.object(Path, "unlink", side_effect=OSError):
            remove_running(server)
        self.both(server.server_port)


if __name__ == "__main__":
    unittest.main()
