from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

ALLOWED_COMMANDS: frozenset[str] = frozenset({"doctor", "context"})
DOCTOR_CACHE_SECONDS: float = 30.0


class RuntimeUnavailable(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class BeyinRuntime:
    def __init__(
        self,
        vault: Path,
        python: str = sys.executable,
        script: Path | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.vault = Path(vault).resolve()
        self.python = python
        self.script = Path(script).resolve() if script is not None else self.vault / "beyin.py"
        self.timeout = timeout
        self.last_error: str | None = None
        self._lock = RLock()
        self._doctor_result: dict[str, object] | None = None
        self._doctor_at: float | None = None

    @property
    def available(self) -> bool:
        return self.script.is_file()

    def doctor(self) -> dict[str, object] | None:
        with self._lock:
            if (
                self._doctor_at is not None
                and time.monotonic() - self._doctor_at < DOCTOR_CACHE_SECONDS
            ):
                return self._doctor_result
            try:
                self._doctor_result = self._run("doctor")
            except RuntimeUnavailable as error:
                self._doctor_result = None
                self.last_error = error.code
            else:
                self.last_error = None
            self._doctor_at = time.monotonic()
            return self._doctor_result

    def context(
        self,
        query: str,
        project: str | None = None,
        limit: int = 20,
        budget_chars: int = 20000,
    ) -> dict[str, object]:
        arguments = ["--no-sync", "--limit", str(limit), "--budget-chars", str(budget_chars)]
        if project is not None:
            arguments.extend(["--project", project])
        arguments.extend(["--", query])
        return self._run("context", arguments)

    def _run(
        self, command: str, arguments: Sequence[str] = ()
    ) -> dict[str, object]:
        if command not in ALLOWED_COMMANDS:
            raise ValueError(f"Unsupported command: {command}")
        # Keep both safety arguments mandatory even for internal calls.
        if command == "context" and (
            len(arguments) < 3 or arguments[0] != "--no-sync" or arguments[-2] != "--"
        ):
            raise ValueError("Context requires --no-sync and a query after --")
        with self._lock:
            if not self.available:
                raise RuntimeUnavailable("missing")
            environment = os.environ.copy()
            environment["PYTHONUTF8"] = "1"
            try:
                result = subprocess.run(
                    [self.python, str(self.script), command, *arguments],
                    shell=False,
                    cwd=self.vault,
                    capture_output=True,
                    encoding="utf-8",
                    timeout=self.timeout,
                    env=environment,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise RuntimeUnavailable("timeout") from error
            except UnicodeError as error:
                raise RuntimeUnavailable("bad_output") from error
            except OSError as error:
                raise RuntimeUnavailable("failed") from error
            if result.returncode != 0:
                raise RuntimeUnavailable("failed")
            try:
                output = json.loads(result.stdout.lstrip("\ufeff"))
            except (ValueError, RecursionError) as error:
                raise RuntimeUnavailable("bad_output") from error
            if not isinstance(output, dict):
                raise RuntimeUnavailable("bad_output")
            return output


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _iso_timestamp(value: object) -> str | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def health_summary(doctor: Mapping[str, object] | None) -> dict[str, object]:
    """Return version, sync and companion details with nullable missing fields."""
    report = _mapping(doctor)
    updates = _mapping(report.get("updates"))
    hook = _mapping(report.get("hook-health.json"))
    sync = _mapping(hook.get("sync"))
    companion = _mapping(report.get("companion_hygiene"))
    limits = _mapping(companion.get("limits"))
    raw_files = companion.get("files")
    files: dict[str, object] | None = None
    if isinstance(raw_files, Mapping):
        files = {}
        for name, details in raw_files.items():
            detail = _mapping(details)
            files[name] = {
                "chars": detail.get("chars"),
                "limit": detail.get("limit", limits.get(name)),
                "over_limit": detail.get("over_limit"),
            }
    update_status = updates.get("status")
    return {
        "installed_version": updates.get("current_version"),
        "latest_version": updates.get("version"),
        "up_to_date": update_status == "up_to_date" if update_status is not None else None,
        "checked_at": _iso_timestamp(updates.get("checked_at")),
        "last_sync_at": _iso_timestamp(hook.get("at")),
        "last_sync_status": sync.get("status"),
        "potential_missing_receipts": report.get("potential_missing_receipts"),
        "memory_files": files,
        "memory_limits": companion.get("limits"),
        "companion_dir": companion.get("directory"),
    }
