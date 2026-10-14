from __future__ import annotations

import argparse
import errno
import http.client
import json
import os
import shutil
import socket
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
from beyin_web.domain.obsidian import obsidian_vault_uri
from beyin_web.http.server import BeyinHTTPServer, create_server
from beyin_web.install import install, uninstall
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
        "install_exclusive": "--install ile --uninstall birlikte verilemez",
        "not_beyin": "Uyarı: bu klasörde beyin.py yok. Arayüz Beyin'in yazdığı kayıtları gösterir; önce Beyin'i kurun.",
        "installed": "beyin-web kuruldu. Açmak için kısayola tıklayın:",
        "installed_plain": "beyin-web kuruldu, ama bu ortamda kısayol oluşturulamadı. Açmak için: beyin-web --open",
        "install_failed": "Kurulum tamamlanamadı. Klasör izinlerini denetleyip yeniden deneyin.",
        "uninstalled": "beyin-web kaldırıldı. Ayarlar ve vault'unuz yerinde duruyor. Silinenler:",
        "uninstall_failed": "Kaldırma tamamlanamadı. Arayüz açıksa kapatıp yeniden deneyin.",
        "shortcut_description": "Beyin'in web arayüzünü açar",
    },
    "en": {
        "port_range": "the port must be between 0 and 65535",
        "idle_positive": "the idle exit time must be positive",
        "vault_missing": "Vault not found. Point --vault at an existing vault folder.",
        "plain_mode": "Beyin not found; running in plain mode.",
        "server_failed": "The server could not start. Check the settings and the available ports.",
        "address": "beyin-web address: {address}",
        "browser_failed": "The browser could not be opened. Open the address shown here in a browser.",
        "install_exclusive": "--install and --uninstall cannot be given together",
        "not_beyin": "Warning: this folder has no beyin.py. The interface shows what Beyin writes; install Beyin first.",
        "installed": "beyin-web is installed. Click the shortcut to open it:",
        "installed_plain": "beyin-web is installed, but no shortcut could be made here. To open it: beyin-web --open",
        "install_failed": "The installation could not finish. Check the folder permissions and try again.",
        "uninstalled": "beyin-web is removed. Your settings and your vault are untouched. Deleted:",
        "uninstall_failed": "The removal could not finish. Close the interface if it is open and try again.",
        "shortcut_description": "Opens the web interface of Beyin",
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
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
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
    if args.install and args.uninstall:
        parser.error(text["install_exclusive"])
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


def notify(message: str) -> None:
    """Say why nothing opened. A shortcut runs without a console, so there the message is a dialog."""
    if sys.stderr is not None:
        print(message, file=sys.stderr)
    elif os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "beyin-web", 0x10)
        except (AttributeError, OSError):
            pass


def find_running(settings: Settings) -> int | None:
    """Return the port of a server that already shows this vault, looking only at ports that are taken."""
    if settings.port == 0:
        return None
    expected = obsidian_vault_uri(str(settings.vault))
    for port in range(settings.port, min(settings.port + 20, 65535) + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                pass
            else:
                # Servers take the first free port, so nothing of ours listens beyond a free one.
                return None
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            headers = {"Cookie": f"bw_session={settings.token}"} if settings.token_enabled else {}
            connection.request("GET", "/api/v1/pulse", headers=headers)
            response = connection.getresponse()
            body = response.read(65536)
            if response.status == 200 and json.loads(body).get("obsidian_uri") == expected:
                return port
        except (OSError, ValueError, AttributeError, http.client.HTTPException):
            pass
        finally:
            connection.close()
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
        viewer = shutil.which("wslview")
        if viewer:
            command = [viewer, address]
        else:
            # Not explorer.exe: it takes an address with a query string for a folder and opens Documents (measured).
            handler = shutil.which("rundll32.exe") or "/mnt/c/Windows/System32/rundll32.exe"
            command = [handler, "url.dll,FileProtocolHandler", address]
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    # Piped to another program on Windows, stdout takes the ANSI code page, which has no "ı" or "İ";
    # a Turkish message must not crash the command after its work is done.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = parse_args(argv)
    directory = config_directory()
    text = MESSAGES[resolve_language(args.lang, read_config(directory / "config.json"))]
    if args.uninstall:
        try:
            removed = uninstall()
        except (OSError, ValueError, subprocess.SubprocessError):
            notify(text["uninstall_failed"])
            return 2
        print("\n".join([text["uninstalled"], *removed]), flush=True)
        return 0
    vault = resolve_vault(args.vault, os.environ, Path.cwd(), directory / "config.json")
    if vault is None or not vault.is_dir():
        notify(text["vault_missing"])
        return 2
    if args.install:
        if not (vault / "beyin.py").is_file():
            notify(text["not_beyin"])
        try:
            shortcuts = install(vault.resolve(), directory, language=args.lang,
                                description=text["shortcut_description"])
        except (OSError, ValueError, subprocess.SubprocessError):
            notify(text["install_failed"])
            return 2
        print("\n".join([text["installed"], *shortcuts]) if shortcuts else text["installed_plain"], flush=True)
        return 0
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
        running = find_running(settings) if args.reuse else None
        if running is not None:
            address = f"http://127.0.0.1:{running}/"
            if settings.token_enabled:
                address += "?" + urlencode({"t": settings.token})
            print(text["address"].format(address=address), flush=True)
            if settings.open_browser:
                open_address(address)
            return 0
        runtime = BeyinRuntime(settings.vault, enabled=settings.beyin_enabled)
        if not runtime.available and sys.stderr is not None:
            print(text["plain_mode"], file=sys.stderr)
        companion_dir = health_summary(runtime.doctor() if runtime.available else None)["companion_dir"]
        source = MarkdownSource(
            settings.vault, companion_dir=companion_dir if isinstance(companion_dir, str) else None,
        )
        server = bind_server(settings, source, runtime)
    except (OSError, ValueError):
        notify(text["server_failed"])
        return 2
    address = f"http://127.0.0.1:{server.server_address[1]}/"
    if settings.token_enabled:
        address += "?" + urlencode({"t": settings.token})
    print(text["address"].format(address=address), flush=True)
    if settings.open_browser:
        try:
            open_address(address)
        except OSError:
            notify(text["browser_failed"])
    serve(server, settings.idle_exit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
