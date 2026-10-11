from __future__ import annotations

import contextlib
import io
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from beyin_web.http.server import BeyinHTTPServer, create_server
from scripts import measure
from tests.support import FIXTURES, make_vault

ROOT = Path(__file__).resolve().parents[1]
TIMING = re.compile(r"^api (.+): first_ms=(\d+\.\d+) median_ms=(\d+\.\d+) "
                    r"max_ms=(\d+\.\d+) status=(\d+)$", re.MULTILINE)


class MeasureTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.vault = make_vault(self.tmp)

    def run_measure(self, *args: str, vault: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "measure.py"),
                               str(vault or self.vault), *args], cwd=self.tmp,
                              capture_output=True, encoding="utf-8", env=env,
                              timeout=30, check=False)

    def file_state(self) -> dict[str, tuple[int, int, bytes]]:
        return {path.relative_to(self.vault).as_posix():
                (path.stat().st_mtime_ns, path.stat().st_ctime_ns, path.read_bytes())
                for path in self.vault.rglob("*") if path.is_file() and not path.is_symlink()}

    def test_api_timings_and_read_only_vault(self) -> None:
        before = self.file_state()
        result = self.run_measure("--api", "--no-beyin", "--repeat", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        matches = TIMING.findall(result.stdout)
        endpoints = {endpoint.split("?", 1)[0] for endpoint, *_ in matches}
        self.assertEqual(len(matches), 13, result.stdout)
        self.assertTrue({"/pulse", "/home", "/projects", "/tasks", "/knowledge",
                         "/journal/heatmap", "/graph", "/search", "/memory"} <= endpoints)
        for prefix in ("/projects/", "/records/", "/journal/months/", "/journal/days/"):
            self.assertEqual(sum(endpoint.startswith(prefix) for endpoint in endpoints), 1)
        for endpoint, first, middle, maximum, status in matches:
            with self.subTest(endpoint=endpoint):
                self.assertEqual(status, "200")
                self.assertGreaterEqual(float(first), 0)
                self.assertLessEqual(float(middle), float(maximum))
        self.assertIn("api /health: atlandı", result.stdout)
        self.assertIn("api /search?mode=beyin: atlandı", result.stdout)
        self.assertRegex(result.stdout, r"rss_mb: (?:unavailable|\d+\.\d+)")
        self.assertEqual(before, self.file_state())

    def test_empty_vault_skips_parameterized_endpoints(self) -> None:
        empty = self.tmp / "empty"
        empty.mkdir()
        result = self.run_measure("--api", "--no-beyin", "--repeat", "2", vault=empty)
        self.assertEqual(result.returncode, 0, result.stderr)
        for endpoint in ("/projects/<project>", "/records/<rid>", "/journal/months/<month>",
                         "/journal/days/<day>", "/search", "/search?mode=beyin", "/health"):
            self.assertIn(f"api {endpoint}: atlandı", result.stdout)
        self.assertEqual(len(TIMING.findall(result.stdout)), 8, result.stdout)
        self.assertTrue(all(row[-1] == "200" for row in TIMING.findall(result.stdout)))
        self.assertEqual(list(empty.iterdir()), [])

    def test_idle_with_and_without_api(self) -> None:
        before = self.file_state()
        for args in (("--idle", "0.2"), ("--api", "--repeat", "2", "--idle", "0.2")):
            with self.subTest(args=args):
                result = self.run_measure("--no-beyin", *args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertRegex(result.stdout, r"idle_cpu_percent: \d+\.\d+")
                if "--api" not in args:
                    self.assertNotIn("api /", result.stdout)
        self.assertEqual(before, self.file_state())

    def test_no_beyin_never_calls_cli_and_closes_port(self) -> None:
        script = (FIXTURES / "fake_beyin.py").read_text(encoding="utf-8")
        (self.vault / "beyin.py").write_text(script, encoding="utf-8")
        before = self.file_state()
        servers: list[BeyinHTTPServer] = []
        original_threads = set(threading.enumerate())

        def capture(*args: object, **kwargs: object) -> object:
            server = create_server(*args, **kwargs)
            self.assertIsInstance(server, BeyinHTTPServer)
            servers.append(server)
            return server

        with patch.object(measure, "create_server", side_effect=capture), \
                patch("beyin_web.runtime.beyin_cli.subprocess.run", side_effect=AssertionError("CLI called")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(measure.main([str(self.vault), "--api", "--no-beyin", "--repeat", "2"]), 0)
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].socket.fileno(), -1)
        with socket.socket() as connection:
            connection.settimeout(1)
            self.assertNotEqual(connection.connect_ex(servers[0].server_address), 0)
        self.assertFalse(set(threading.enumerate()) - original_threads)
        self.assertEqual(before, self.file_state())

    def test_beyin_uses_only_read_only_commands(self) -> None:
        script = (FIXTURES / "fake_beyin.py").read_text(encoding="utf-8")
        (self.vault / "beyin.py").write_text(script, encoding="utf-8")
        before = self.file_state()
        output = io.StringIO()
        with patch.dict(os.environ, {"FAKE_BEYIN_LOG": "", "FAKE_BEYIN_MODE": "ok"}), \
                patch("beyin_web.runtime.beyin_cli.subprocess.run", wraps=subprocess.run) as run, \
                contextlib.redirect_stdout(output):
            self.assertEqual(measure.main([str(self.vault), "--api", "--repeat", "2"]), 0)
        matches = TIMING.findall(output.getvalue())
        self.assertEqual(len(matches), 15, output.getvalue())
        self.assertTrue(all(row[-1] == "200" for row in matches))
        commands = [call.args[0][2:] for call in run.call_args_list]
        self.assertEqual(sum(command == ["doctor"] for command in commands), 1)
        self.assertEqual(sum(command[0] == "context" for command in commands), 3)
        for command in commands:
            if command[0] == "context":
                self.assertEqual(command[1], "--no-sync")
                self.assertEqual(command[-2], "--")
        self.assertEqual(before, self.file_state())

    def test_server_closes_on_failure(self) -> None:
        with measure.running_server(self.vault, True) as server:
            address = server.server_address
        with socket.socket() as connection:
            self.assertNotEqual(connection.connect_ex(address), 0)
        with self.assertRaisesRegex(RuntimeError, "measurement failed"):
            with measure.running_server(self.vault, True) as server:
                raise RuntimeError("measurement failed")
        self.assertEqual(server.socket.fileno(), -1)

    def test_non_200_response_is_reported_and_measurement_continues(self) -> None:
        output = io.StringIO()
        with measure.running_server(self.vault, True) as server, contextlib.redirect_stdout(output):
            measure.measure_endpoint(server, "/records/missing", 2)
            measure.measure_endpoint(server, "/home", 2)
        matches = TIMING.findall(output.getvalue())
        self.assertEqual([row[-1] for row in matches], ["404", "200"])

    def test_invalid_repeat_and_idle(self) -> None:
        for args in (("--repeat", "0"), ("--idle", "-1"), ("--idle", "nan"), ("--idle", "inf")):
            with self.subTest(args=args):
                result = self.run_measure(*args)
                self.assertEqual(result.returncode, 2)

    def test_rss_uses_proc_status_only(self) -> None:
        with patch.object(Path, "read_text", return_value="Name:\tpython\nVmRSS:\t2048 kB\n") as read:
            self.assertEqual(measure.rss_mb(), 2.0)
            read.assert_called_once_with(encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=OSError("unavailable")):
            self.assertIsNone(measure.rss_mb())


if __name__ == "__main__":
    unittest.main()
