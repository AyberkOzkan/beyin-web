from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
from unittest.mock import patch

from beyin_web.runtime.beyin_cli import (
    ALLOWED_COMMANDS,
    BeyinRuntime,
    RuntimeUnavailable,
    health_summary,
)
from tests.support import FIXTURES, make_vault


class BeyinRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.vault = make_vault(self.tmp)
        self.script = FIXTURES / "fake_beyin.py"
        self.log = self.tmp / "arguments.jsonl"
        environment = patch.dict(os.environ, {
            "FAKE_BEYIN_MODE": "ok", "FAKE_BEYIN_LOG": str(self.log),
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.runtime = BeyinRuntime(self.vault, script=self.script)

    def logged_arguments(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def test_success(self) -> None:
        self.assertTrue(self.runtime.available)
        doctor = self.runtime.doctor()
        self.assertIsNotNone(doctor)
        self.assertEqual(doctor["updates"]["current_version"], "0.1.0")
        self.assertIsNone(self.runtime.last_error)
        context = self.runtime.context("Çınar")
        self.assertEqual(context["records"][0]["text"], "Sentetik bağlam")
        self.assertEqual(context["citations"][0]["id"], "fake-1")
        self.assertFalse(context["abstained"])
        self.assertEqual(context["stale_count"], 0)
        self.assertEqual(context["source_sync"]["status"], "skipped")

    def test_failure_modes(self) -> None:
        for mode, code in (("fail", "failed"), ("badjson", "bad_output"), ("slow", "timeout")):
            with self.subTest(mode=mode), patch.dict(os.environ, {"FAKE_BEYIN_MODE": mode}):
                runtime = BeyinRuntime(self.vault, script=self.script, timeout=0.25 if mode == "slow" else 10)
                with self.assertRaises(RuntimeUnavailable) as caught:
                    runtime.context("sorgu")
                self.assertEqual(caught.exception.code, code)
                self.assertIsNone(runtime.doctor())
                self.assertEqual(runtime.last_error, code)

    def test_missing_script(self) -> None:
        runtime = BeyinRuntime(self.vault)
        self.assertFalse(runtime.available)
        self.assertIsNone(runtime.doctor())
        self.assertEqual(runtime.last_error, "missing")
        with self.assertRaises(RuntimeUnavailable) as caught:
            runtime.context("sorgu")
        self.assertEqual(caught.exception.code, "missing")
        self.assertFalse(self.log.exists())

    def test_default_script_and_python(self) -> None:
        shutil.copyfile(self.script, self.vault / "beyin.py")
        runtime = BeyinRuntime(self.vault)
        self.assertEqual(runtime.python, sys.executable)
        self.assertEqual(runtime.timeout, 10.0)
        self.assertTrue(runtime.available)
        self.assertIsNotNone(runtime.doctor())

    def test_disabled_runtime_never_starts_subprocess(self) -> None:
        shutil.copyfile(self.script, self.vault / "beyin.py")
        runtime = BeyinRuntime(self.vault, enabled=False)
        with patch("beyin_web.runtime.beyin_cli.subprocess.run") as run:
            self.assertFalse(runtime.available)
            self.assertIsNone(runtime.doctor())
            self.assertEqual(runtime.last_error, "missing")
            with self.assertRaises(RuntimeUnavailable) as caught:
                runtime.context("sorgu")
            self.assertEqual(caught.exception.code, "missing")
        run.assert_not_called()
        self.assertFalse(self.log.exists())

    def test_directory_is_not_available(self) -> None:
        (self.vault / "beyin.py").mkdir()
        self.assertFalse(BeyinRuntime(self.vault).available)

    def test_exact_arguments_and_only_read_only_commands(self) -> None:
        self.runtime.doctor()
        self.runtime.context("-tire ile başlayan")
        self.runtime.context("İş parçacığı", project="Çınar Projesi", limit=3, budget_chars=800)
        self.assertEqual(self.logged_arguments(), [
            ["doctor"],
            ["context", "--no-sync", "--limit", "20", "--budget-chars", "20000", "--", "-tire ile başlayan"],
            ["context", "--no-sync", "--limit", "3", "--budget-chars", "800", "--project", "Çınar Projesi", "--", "İş parçacığı"],
        ])
        self.assertEqual(ALLOWED_COMMANDS, frozenset({"doctor", "context"}))

    def test_disallowed_command_is_rejected_before_subprocess(self) -> None:
        with patch("beyin_web.runtime.beyin_cli.subprocess.run") as run:
            with self.assertRaises(ValueError):
                self.runtime._run("unsupported")
            with self.assertRaises(ValueError):
                self.runtime._run("context", ["--", "sorgu"])
            with self.assertRaises(ValueError):
                self.runtime._run("context", ["--no-sync", "sorgu"])
        run.assert_not_called()

    def test_doctor_cache_expires_at_thirty_seconds(self) -> None:
        with patch("beyin_web.runtime.beyin_cli.time.monotonic", return_value=0.0) as clock:
            first = self.runtime.doctor()
            clock.return_value = 29.999
            self.assertEqual(self.runtime.doctor(), first)
            self.assertEqual(self.logged_arguments(), [["doctor"]])
            clock.return_value = 30.0
            self.assertEqual(self.runtime.doctor(), first)
        self.assertEqual(self.logged_arguments(), [["doctor"], ["doctor"]])

    def test_failed_doctor_cache_recovers_after_expiry(self) -> None:
        with patch("beyin_web.runtime.beyin_cli.time.monotonic", return_value=0.0) as clock:
            with patch.dict(os.environ, {"FAKE_BEYIN_MODE": "fail"}):
                self.assertIsNone(self.runtime.doctor())
            self.assertIsNone(self.runtime.doctor())
            self.assertEqual(self.runtime.last_error, "failed")
            self.assertEqual(self.logged_arguments(), [["doctor"]])
            clock.return_value = 30.0
            self.assertIsNotNone(self.runtime.doctor())
            self.assertIsNone(self.runtime.last_error)

    def test_subprocess_settings_and_unchanged_context(self) -> None:
        expected = {"records": [], "abstained": True, "future_field": {"value": 5}}
        result = subprocess.CompletedProcess([], 0, json.dumps(expected), "")
        with patch.dict(os.environ, {"PYTHONUTF8": "0", "FAKE_INHERITED": "value"}):
            with patch("beyin_web.runtime.beyin_cli.subprocess.run", return_value=result) as run:
                self.assertEqual(self.runtime.context("sorgu"), expected)
        kwargs = run.call_args.kwargs
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["cwd"], self.vault)
        self.assertTrue(kwargs["capture_output"])
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["timeout"], 10.0)
        self.assertEqual(kwargs["env"]["PYTHONUTF8"], "1")
        self.assertEqual(kwargs["env"]["FAKE_INHERITED"], "value")

    def test_bom_and_crlf_output(self) -> None:
        result = subprocess.CompletedProcess([], 0, '\ufeff{\r\n"text": "Çınar"\r\n}\r\n', "")
        with patch("beyin_web.runtime.beyin_cli.subprocess.run", return_value=result):
            self.assertEqual(self.runtime.context("sorgu"), {"text": "Çınar"})

    def test_non_object_json_is_bad_output(self) -> None:
        for output in ("null", "[]", '"text"', "42"):
            with self.subTest(output=output):
                result = subprocess.CompletedProcess([], 0, output, "")
                with patch("beyin_web.runtime.beyin_cli.subprocess.run", return_value=result):
                    with self.assertRaises(RuntimeUnavailable) as caught:
                        self.runtime.context("sorgu")
                self.assertEqual(caught.exception.code, "bad_output")

    def test_process_and_decoding_errors(self) -> None:
        for error, code in ((OSError("unavailable"), "failed"), (UnicodeError("invalid UTF-8"), "bad_output")):
            with self.subTest(code=code):
                with patch("beyin_web.runtime.beyin_cli.subprocess.run", side_effect=error):
                    with self.assertRaises(RuntimeUnavailable) as caught:
                        self.runtime.context("sorgu")
                self.assertEqual(caught.exception.code, code)

    def test_concurrent_calls_are_serialized_and_doctor_cache_is_shared(self) -> None:
        barrier = Barrier(4)
        counter_lock = Lock()
        active = 0
        maximum = 0

        def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal active, maximum
            with counter_lock:
                active += 1
                maximum = max(maximum, active)
            try:
                time.sleep(0.03)
                return subprocess.CompletedProcess([], 0, "{}", "")
            finally:
                with counter_lock:
                    active -= 1

        def call(index: int) -> dict[str, object] | None:
            barrier.wait(timeout=5)
            return self.runtime.doctor() if index < 2 else self.runtime.context("sorgu")

        with patch("beyin_web.runtime.beyin_cli.subprocess.run", side_effect=run) as process:
            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertEqual(list(pool.map(call, range(4))), [{}, {}, {}, {}])
        self.assertEqual(maximum, 1)
        self.assertEqual(process.call_count, 3)

    def test_vault_files_remain_unchanged(self) -> None:
        def snapshot() -> dict[Path, tuple[bytes, int]]:
            return {
                path.relative_to(self.vault): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.vault.rglob("*") if not path.is_symlink() and path.is_file()
            }

        before = snapshot()
        self.runtime.doctor()
        self.runtime.context("sorgu")
        self.assertEqual(snapshot(), before)


class HealthSummaryTests(unittest.TestCase):
    def test_missing_fields_are_none(self) -> None:
        summary = health_summary({})
        self.assertTrue(summary)
        self.assertTrue(all(value is None for value in summary.values()))

    def test_measured_shape_with_synthetic_values(self) -> None:
        summary = health_summary({
            "updates": {"current_version": "1.0", "version": "2.0", "status": "available", "checked_at": 0},
            "hook-health.json": {"at": 1767225600.0, "sync": {"status": "succeeded"}},
            "potential_missing_receipts": 2,
            "companion_hygiene": {
                "directory": "🔮 850-Companion", "limits": {"Threads.md": 200},
                "files": {
                    "Core.md": {"chars": 90},
                    "Threads.md": {"chars": 210, "limit": 200, "over_limit": True},
                },
            },
        })
        self.assertEqual(summary, {
            "installed_version": "1.0", "latest_version": "2.0", "up_to_date": False,
            "checked_at": "1970-01-01T00:00:00+00:00",
            "last_sync_at": "2026-01-01T00:00:00+00:00", "last_sync_status": "succeeded",
            "potential_missing_receipts": 2, "companion_dir": "🔮 850-Companion",
            "memory_limits": {"Threads.md": 200},
            "memory_files": {
                "Core.md": {"chars": 90, "limit": None, "over_limit": None},
                "Threads.md": {"chars": 210, "limit": 200, "over_limit": True},
            },
        })
        self.assertTrue(health_summary({"updates": {"status": "up_to_date"}})["up_to_date"])

    def test_null_and_unexpected_nested_values(self) -> None:
        for value in (None, [], "unexpected", 5):
            with self.subTest(value=value):
                summary = health_summary({
                    "updates": value, "hook-health.json": value,
                    "hook-error.json": value, "companion_hygiene": value,
                })
                self.assertTrue(all(field is None for field in summary.values()))
        self.assertEqual(health_summary(None), health_summary({}))

    def test_partial_companion_files_and_limits(self) -> None:
        summary = health_summary({"companion_hygiene": {
            "files": {"Threads.md": {}, "Core.md": None}, "limits": {"Threads.md": 100},
        }})
        self.assertEqual(summary["memory_files"]["Threads.md"], {
            "chars": None, "limit": 100, "over_limit": None,
        })
        self.assertEqual(summary["memory_files"]["Core.md"], {
            "chars": None, "limit": None, "over_limit": None,
        })

    def test_invalid_timestamps_are_none(self) -> None:
        for value in (None, "yesterday", True, float("nan"), float("inf"), 10**100):
            with self.subTest(value=value):
                summary = health_summary({
                    "updates": {"checked_at": value}, "hook-health.json": {"at": value},
                })
                self.assertIsNone(summary["checked_at"])
                self.assertIsNone(summary["last_sync_at"])


if __name__ == "__main__":
    unittest.main()
