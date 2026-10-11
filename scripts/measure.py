from __future__ import annotations

import argparse
import http.client
import json
import math
import re
import sys
import threading
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import cast
from urllib.parse import quote, urlencode


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beyin_web.config import Settings
from beyin_web.domain.receipts import build_receipts
from beyin_web.http.server import BeyinHTTPServer, create_server
from beyin_web.runtime.beyin_cli import BeyinRuntime, health_summary
from beyin_web.vault.records import classify
from beyin_web.vault.scan import MarkdownSource, VaultSnapshot


@contextmanager
def running_server(vault: Path, no_beyin: bool) -> Iterator[BeyinHTTPServer]:
    runtime = BeyinRuntime(vault, enabled=not no_beyin)
    companion = health_summary(runtime.doctor() if runtime.available else None)["companion_dir"]
    source = MarkdownSource(vault, companion_dir=companion if isinstance(companion, str) else None)
    server = cast(BeyinHTTPServer, create_server(
        Settings(vault, port=0, token_enabled=False, beyin_enabled=not no_beyin), source, runtime,
    ))
    thread = threading.Thread(target=server.serve_forever)
    started = False
    try:
        thread.start()
        started = True
        yield server
    finally:
        try:
            if started:
                server.shutdown()
                thread.join()
        finally:
            server.server_close()


def request(server: BeyinHTTPServer, endpoint: str) -> tuple[float, int, dict[str, object]]:
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=30)
    try:
        start = perf_counter()
        connection.request("GET", "/api/v1" + endpoint)
        response = connection.getresponse()
        body = response.read()
        elapsed = (perf_counter() - start) * 1000
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeError):
            payload = {}
        return elapsed, response.status, payload if isinstance(payload, dict) else {}
    finally:
        connection.close()


def measure_endpoint(server: BeyinHTTPServer, endpoint: str, repeat: int) -> dict[str, object]:
    first_ms, status, payload = request(server, endpoint)
    samples: list[float] = []
    statuses = {status}
    for _ in range(repeat):
        elapsed, current_status, _ = request(server, endpoint)
        samples.append(elapsed)
        statuses.add(current_status)
    extra = "" if len(statuses) == 1 else " statuses=" + ",".join(map(str, sorted(statuses)))
    print(f"api {endpoint}: first_ms={first_ms:.3f} median_ms={median(samples):.3f} "
          f"max_ms={max(samples):.3f} status={status}{extra}")
    return payload


def skipped(endpoint: str, reason: str) -> None:
    print(f"api {endpoint}: atlandı ({reason})")


def measure_api(server: BeyinHTTPServer, snapshot: VaultSnapshot, repeat: int) -> None:
    for endpoint in ("/pulse", "/home"):
        measure_endpoint(server, endpoint, repeat)
    projects = measure_endpoint(server, "/projects", repeat).get("projects")
    first_project = projects[0] if isinstance(projects, list) and projects else None
    name = first_project.get("name") if isinstance(first_project, dict) else None
    if isinstance(name, str) and name:
        measure_endpoint(server, "/projects/" + quote(name, safe=""), repeat)
    else:
        skipped("/projects/<project>", "proje yok")
    for endpoint in ("/tasks", "/knowledge"):
        measure_endpoint(server, endpoint, repeat)
    records = sorted(snapshot.records.values(), key=lambda record: record.path)
    if records:
        measure_endpoint(server, "/records/" + quote(records[0].rid, safe=""), repeat)
    else:
        skipped("/records/<rid>", "kayıt yok")
    known_projects = {record.project for record in records
                      if record.project and classify(record) not in {"index", "rejected", "receipt"}}
    receipts, _ = build_receipts(snapshot, known_projects)
    if receipts:
        day = receipts[0].created_at.astimezone().date().isoformat()
        measure_endpoint(server, "/journal/months/" + day[:7], repeat)
        measure_endpoint(server, "/journal/days/" + day, repeat)
    else:
        skipped("/journal/months/<month>", "receipt yok")
        skipped("/journal/days/<day>", "receipt yok")
    for endpoint in ("/journal/heatmap", "/graph"):
        measure_endpoint(server, endpoint, repeat)
    word = next((match.group() for record in records
                 if (match := re.search(r"[^\W_]+", record.title))), None)
    query = urlencode({"q": word}) if word else None
    if query:
        measure_endpoint(server, "/search?" + query, repeat)
    else:
        skipped("/search", "başlıklarda arama sözcüğü yok")
    if not server.runtime.available:
        skipped("/search?mode=beyin", "Beyin yok veya devre dışı")
    elif query:
        measure_endpoint(server, "/search?" + query + "&mode=beyin", repeat)
    else:
        skipped("/search?mode=beyin", "başlıklarda arama sözcüğü yok")
    measure_endpoint(server, "/memory", repeat)
    if server.runtime.available:
        measure_endpoint(server, "/health", repeat)
    else:
        skipped("/health", "Beyin yok veya devre dışı")


def rss_mb() -> float | None:
    try:
        status = Path("/proc/self/status").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    match = re.search(r"^VmRSS:\s+(\d+)\s+kB\s*$", status, re.MULTILINE)
    return int(match[1]) / 1024 if match else None


def print_rss() -> None:
    value = rss_mb()
    print("rss_mb: unavailable" if value is None else f"rss_mb: {value:.3f}")


def measure_idle(seconds: float) -> None:
    start = perf_counter()
    cpu_start = time.process_time()
    time.sleep(seconds)
    cpu = time.process_time() - cpu_start
    elapsed = perf_counter() - start
    print(f"idle_cpu_percent: {cpu / elapsed * 100:.3f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure read-only vault scans and local API responses.")
    parser.add_argument("vault", type=Path)
    parser.add_argument("--api", action="store_true")
    parser.add_argument("--repeat", type=int, default=20, metavar="N")
    parser.add_argument("--no-beyin", action="store_true")
    parser.add_argument("--idle", type=float, metavar="SECONDS")
    args = parser.parse_args(argv)
    if not args.vault.is_dir():
        parser.error("vault must be an existing directory")
    if args.repeat < 1:
        parser.error("repeat must be positive")
    if args.idle is not None and (not math.isfinite(args.idle) or args.idle < 0):
        parser.error("idle must be a finite non-negative number")
    source = MarkdownSource(args.vault, min_interval=0)
    start = perf_counter()
    source.snapshot()
    cold_ms = (perf_counter() - start) * 1000
    start = perf_counter()
    snapshot = source.snapshot()
    warm_ms = (perf_counter() - start) * 1000
    print(f"cold_ms: {cold_ms:.3f}")
    print(f"warm_ms: {warm_ms:.3f}")
    for kind, count in sorted(Counter(record.kind for record in snapshot.records.values()).items()):
        print(f"{kind}: {count}")
    print(f"warnings: {len(snapshot.warnings)}")
    if args.api or args.idle is not None:
        with running_server(args.vault.resolve(), args.no_beyin) as server:
            if args.api:
                measure_api(server, snapshot, args.repeat)
            if args.idle is not None:
                measure_idle(args.idle)
            print_rss()
    else:
        print_rss()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
