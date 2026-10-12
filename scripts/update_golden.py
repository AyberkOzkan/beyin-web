from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beyin_web.config import Settings
from beyin_web.domain.obsidian import obsidian_uri, obsidian_vault_uri
from beyin_web.http.api import register_api
from beyin_web.http.server import BeyinHTTPServer
from beyin_web.runtime.beyin_cli import BeyinRuntime
from beyin_web.vault.records import make_rid
from beyin_web.vault.scan import MarkdownSource, VaultSnapshot
from tests.support import FIXTURES, make_vault

TZ = timezone(timedelta(hours=3))
NOW = datetime(2026, 1, 12, 16, tzinfo=TZ)
ENDPOINTS: dict[str, str] = {
    "pulse": "/pulse", "home": "/home", "projects": "/projects",
    "project": "/projects/atlas", "tasks": "/tasks", "knowledge": "/knowledge",
    "record": "/records/" + make_rid("notes/atlas.md"),
    "journal_month": "/journal/months/2026-01", "journal_day": "/journal/days/2026-01-12",
    "journal_heatmap": "/journal/heatmap", "graph": "/graph",
    "search": "/search?q=Atlas", "search_beyin": "/search?q=Atlas&mode=beyin",
    "memory": "/memory", "health": "/health",
    "reports": "/reports?week=2026-01-07",
}


class ClockedSource:
    def __init__(self, vault: Path, clock: Callable[[], datetime]) -> None:
        self.source = MarkdownSource(vault, min_interval=0)
        self.clock = clock
        self._snapshot: VaultSnapshot | None = None

    def snapshot(self) -> VaultSnapshot:
        snapshot = self.source.snapshot()
        if self._snapshot is None or self._snapshot.generation != snapshot.generation:
            self._snapshot = replace(snapshot, scanned_at=self.clock())
        return self._snapshot


@contextmanager
def running_server(
    vault: Path, *, clock: Callable[[], datetime] = lambda: NOW, beyin: bool = True,
) -> Iterator[BeyinHTTPServer]:
    source = ClockedSource(vault, clock)
    runtime = BeyinRuntime(vault, script=FIXTURES / "fake_beyin.py" if beyin else vault / "beyin.py")
    server = BeyinHTTPServer(Settings(vault, port=0, token_enabled=False, display_name="Deniz"), source, runtime)
    register_api(server, clock=clock, tz=TZ)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def request(
    server: BeyinHTTPServer, endpoint: str, etag: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request("GET", "/api/v1" + endpoint, headers={"If-None-Match": etag} if etag else {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def normalize(payload: dict[str, object], vault: Path) -> dict[str, object]:
    if "obsidian_uri" not in payload:
        return payload
    if "path" not in payload:
        if payload["obsidian_uri"] != obsidian_vault_uri(str(vault)):
            raise RuntimeError("invalid obsidian_uri")
        return {**payload, "obsidian_uri": obsidian_vault_uri("/vault")}
    path = payload["path"]
    if not isinstance(path, str) or payload["obsidian_uri"] != obsidian_uri(str(vault), path):
        raise RuntimeError("invalid obsidian_uri")
    return {**payload, "obsidian_uri": obsidian_uri("/vault", path)}


def main() -> int:
    destination = FIXTURES / "golden"
    destination.mkdir(exist_ok=True)
    changed = 0
    with tempfile.TemporaryDirectory() as temporary, patch.dict("os.environ", {
        "FAKE_BEYIN_MODE": "ok", "FAKE_BEYIN_SOURCE": "notes/Çınar Projesi.md",
        "FAKE_BEYIN_TEXT": "Sentetik bağlam", "FAKE_BEYIN_LOG": "",
    }):
        vault = make_vault(Path(temporary))
        with running_server(vault) as server:
            for name, endpoint in ENDPOINTS.items():
                status, _, body = request(server, endpoint)
                if status != 200:
                    raise RuntimeError(f"{name}: HTTP {status}")
                payload = normalize(json.loads(body), vault)
                content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
                if str(vault) in content or vault.as_posix() in content:
                    raise RuntimeError(f"{name}: absolute vault path")
                path = destination / f"{name}.json"
                if not path.exists() or path.read_text(encoding="utf-8") != content:
                    path.write_text(content, encoding="utf-8", newline="\n")
                    changed += 1
    print(f"golden_files={len(ENDPOINTS)} changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
