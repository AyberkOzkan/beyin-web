from __future__ import annotations

import http.client
import json
import os
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from beyin_web.domain.obsidian import obsidian_vault_uri

if TYPE_CHECKING:
    from beyin_web.http.server import BeyinHTTPServer


def read_running(path: Path) -> dict[str, object] | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        value = json.loads(path.read_text(encoding="utf-8").lstrip("\ufeff"))
        if not isinstance(value, dict):
            return None
        if (type(value.get("schema")) is not int or value["schema"] != 1
                or type(value.get("port")) is not int or not 1 <= value["port"] <= 65535
                or path.name != f'{value["port"]}.json'
                or type(value.get("pid")) is not int or value["pid"] <= 0
                or not isinstance(value.get("vault"), str) or not Path(value["vault"]).is_absolute()
                or not isinstance(value.get("session"), str)
                or re.fullmatch(r"[A-Za-z0-9_-]{0,256}", value["session"]) is None):
            return None
        return value
    except (OSError, ValueError, UnicodeError, RuntimeError):
        return None


def write_running(server: BeyinHTTPServer) -> None:
    temporary: Path | None = None
    try:
        directory = server.settings.config_dir / "running"
        directory.mkdir(parents=True, exist_ok=True)
        port = server.server_address[1]
        descriptor, name = tempfile.mkstemp(dir=directory, suffix=".tmp")
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"schema": 1, "port": port, "pid": os.getpid(),
                       "vault": str(server.settings.vault.resolve()),
                       "session": server.session if server.settings.token_enabled else ""}, stream)
        if os.name != "nt":
            try:
                temporary.chmod(0o600)
            except (OSError, NotImplementedError):
                pass
        os.replace(temporary, directory / f"{port}.json")
    except (OSError, ValueError):
        pass
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def remove_running(server: BeyinHTTPServer) -> None:
    path = server.settings.config_dir / "running" / f"{server.server_address[1]}.json"
    value = read_running(path)
    if value is not None and value["session"] == (server.session if server.settings.token_enabled else ""):
        try:
            path.unlink()
        except OSError:
            pass


def find_running(vault: Path, directory: Path) -> int | None:
    vault = vault.resolve()
    expected = obsidian_vault_uri(str(vault))
    try:
        paths = sorted((directory / "running").glob("*.json"))
    except OSError:
        return None
    for path in paths:
        value = read_running(path)
        if value is None or value["vault"] != str(vault):
            continue
        port = int(value["port"])
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            headers = {"Cookie": f'bw_session_{port}={value["session"]}'} if value["session"] else {}
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
