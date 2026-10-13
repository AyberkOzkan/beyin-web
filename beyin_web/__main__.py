from __future__ import annotations

import argparse
import errno
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from collections.abc import Mapping, Sequence
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import urlencode

from beyin_web import __version__
from beyin_web.config import LANGUAGES, Settings, config_directory, load_settings, read_config, resolve_language
from beyin_web.http.server import BeyinHTTPServer, create_server
from beyin_web.runtime.beyin_cli import BeyinRuntime, health_summary
from beyin_web.vault.scan import MarkdownSource, VaultSource

MESSAGES = {
    "tr": {
        "port_range": "port 0 ile 65535 arasında olmalıdır",
        "idle_positive": "boşta kapanma süresi pozitif olmalıdır",
        "vault_missing": "Vault bulunamadı. --vault ile var olan bir vault klasörü belirtin.",
        "plain_mode": "Beyin bulunamadı; yalın kipte çalışıyor.",
        "server_failed": "Sunucu başlatılamadı. Ayarları ve kullanılabilir portları kontrol edin.",
        "address": "beyin-web adresi: {address}",
        "browser_failed": "Tarayıcı açılamadı. Terminaldeki adresi tarayıcıda açın.",
    },
    "en": {
        "port_range": "the port must be between 0 and 65535",
        "idle_positive": "the idle exit time must be positive",
        "vault_missing": "Vault not found. Point --vault at an existing vault folder.",
        "plain_mode": "Beyin not found; running in plain mode.",
        "server_failed": "The server could not start. Check the settings and the available ports.",
        "address": "beyin-web address: {address}",
        "browser_failed": "The browser could not be opened. Open the address shown here in a browser.",
    },
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="beyin-web")
    parser.add_argument("--vault", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--idle-exit", type=int, metavar="DAKİKA")
    parser.add_argument("--no-token", action="store_true")
    parser.add_argument("--no-beyin", action="store_true")
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--lang", choices=LANGUAGES)
    parser.add_argument(
        "--version", action="version", version=f"beyin-web {__version__}"
    )
    args = parser.parse_args(argv)
    text = MESSAGES[args.lang or LANGUAGES[0]]
    args.port_explicit = args.port is not None
    if args.port is None:
        args.port = 7373
    if not 0 <= args.port <= 65535:
        parser.error(text["port_range"])
    if args.idle_exit is not None and args.idle_exit <= 0:
        parser.error(text["idle_positive"])
    return args


def resolve_vault(
    cli_value: str | Path | None,
    env: Mapping[str, str],
    cwd: Path,
    config_path: Path,
) -> Path | None:
    value: str | Path | None = cli_value or env.get("BEYIN_VAULT")
    if not value:
        try:
            config = json.loads(config_path.read_text(encoding="utf-8").lstrip("\ufeff"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            config = None
        if isinstance(config, dict):
            configured_value = config.get("vault")
            if isinstance(configured_value, str) and configured_value:
                value = configured_value
    if value:
        path = Path(value)
        return path if path.is_absolute() else cwd / path
    if (cwd / "beyin.py").is_file() or (cwd / ".obsidian").is_dir():
        return cwd
    return None


def bind_server(
    settings: Settings, source: VaultSource, runtime: BeyinRuntime,
) -> ThreadingHTTPServer:
    for port in range(settings.port, min(settings.port + 20, 65535) + 1):
        try:
            return create_server(replace(settings, port=port), source, runtime)
        except OSError as error:
            # Windows also reports an exclusively occupied port as WSAEACCES.
            if error.errno != errno.EADDRINUSE and getattr(error, "winerror", None) not in {10013, 10048}:
                raise
    raise OSError(errno.EADDRINUSE, "ports_unavailable")


def open_address(address: str) -> None:
    if os.environ.get("WSL_DISTRO_NAME"):
        executable = shutil.which("wslview") or "explorer.exe"
        subprocess.Popen([executable, address], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        webbrowser.open(address)


def _watch_idle(server: BeyinHTTPServer, seconds: float, stopped: threading.Event) -> None:
    with server.activity:
        while not stopped.is_set():
            remaining = seconds - (time.monotonic() - server.last_request)
            if remaining <= 0:
                break
            server.activity.wait(remaining)
        else:
            return
    server.shutdown()


def serve(server: ThreadingHTTPServer, idle_exit: int | None) -> None:
    watcher: threading.Thread | None = None
    stopped: threading.Event | None = None
    application = cast(BeyinHTTPServer, server)
    if idle_exit is not None:
        stopped = threading.Event()
        application.note_request()
        watcher = threading.Thread(
            target=_watch_idle, args=(application, idle_exit * 60, stopped), daemon=True,
        )
        watcher.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if stopped is not None:
            with application.activity:
                stopped.set()
                application.activity.notify_all()
        if watcher is not None:
            watcher.join()
        server.server_close()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    directory = config_directory()
    text = MESSAGES[resolve_language(args.lang, read_config(directory / "config.json"))]
    vault = resolve_vault(args.vault, os.environ, Path.cwd(), directory / "config.json")
    if vault is None or not vault.is_dir():
        print(text["vault_missing"], file=sys.stderr)
        return 2
    try:
        settings = load_settings(
            vault.resolve(), directory,
            port=args.port if args.port_explicit else None,
            token_enabled=not args.no_token,
            idle_exit=args.idle_exit,
            open_browser=args.open,
            beyin_enabled=not args.no_beyin,
            read_only=args.read_only,
            language=args.lang,
        )
        runtime = BeyinRuntime(settings.vault, enabled=settings.beyin_enabled)
        if not runtime.available:
            print(text["plain_mode"], file=sys.stderr)
        companion_dir = health_summary(runtime.doctor() if runtime.available else None)["companion_dir"]
        source = MarkdownSource(
            settings.vault, companion_dir=companion_dir if isinstance(companion_dir, str) else None,
        )
        server = bind_server(settings, source, runtime)
    except (OSError, ValueError):
        print(text["server_failed"], file=sys.stderr)
        return 2
    address = f"http://127.0.0.1:{server.server_address[1]}/"
    if settings.token_enabled:
        address += "?" + urlencode({"t": settings.token})
    print(text["address"].format(address=address), flush=True)
    if settings.open_browser:
        try:
            open_address(address)
        except OSError:
            print(text["browser_failed"], file=sys.stderr)
    serve(server, settings.idle_exit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
