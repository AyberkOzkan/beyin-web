from __future__ import annotations

import json
import os
import secrets
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

# The first language is the default; each one has a static/i18n/<code>.json file.
LANGUAGES = ("tr", "en")


@dataclass(frozen=True)
class Settings:
    vault: Path
    port: int = 7373
    token_enabled: bool = True
    token: str = ""
    idle_exit: int | None = None
    open_browser: bool = False
    display_name: str = ""
    static_dir: Path = field(default_factory=lambda: Path(__file__).parent / "static")
    beyin_enabled: bool = True
    read_only: bool = False
    language: str = LANGUAGES[0]


def config_directory(
    env: Mapping[str, str] | None = None, platform: str | None = None,
) -> Path:
    environment = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if platform == "win32" and environment.get("APPDATA"):
        return Path(environment["APPDATA"]) / "beyin-web"
    if platform != "win32" and environment.get("XDG_CONFIG_HOME"):
        return Path(environment["XDG_CONFIG_HOME"]) / "beyin-web"
    return Path.home() / ".config" / "beyin-web"


def read_config(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8").lstrip("\ufeff"))
    except (OSError, UnicodeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def resolve_language(cli_value: str | None, config: Mapping[str, object]) -> str:
    for value in (cli_value, config.get("language")):
        if isinstance(value, str) and value in LANGUAGES:
            return value
    return LANGUAGES[0]


def load_token(directory: Path) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "token"
    try:
        # Exclusive creation keeps concurrent starts from replacing the secret.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        token = path.read_text(encoding="utf-8").lstrip("\ufeff").strip()
    else:
        token = secrets.token_urlsafe(32)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(token + "\n")
    if not token or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in token):
        raise ValueError("invalid_token")
    if os.name != "nt":
        try:
            path.chmod(0o600)
        except (OSError, NotImplementedError):
            pass
    return token


def load_settings(
    vault: Path,
    directory: Path,
    *,
    port: int | None = None,
    token_enabled: bool = True,
    idle_exit: int | None = None,
    open_browser: bool = False,
    beyin_enabled: bool = True,
    read_only: bool = False,
    language: str | None = None,
) -> Settings:
    if token_enabled and directory.resolve().is_relative_to(vault.resolve()):
        raise ValueError("config_inside_vault")
    config = read_config(directory / "config.json")
    configured_port = config.get("port", 7373)
    if (
        not isinstance(configured_port, int) or isinstance(configured_port, bool)
        or not 0 <= configured_port <= 65535
    ):
        configured_port = 7373
    display_name = config.get("display_name", "")
    return Settings(
        vault=vault,
        port=configured_port if port is None else port,
        token_enabled=token_enabled,
        token=load_token(directory) if token_enabled else "",
        idle_exit=idle_exit,
        open_browser=open_browser,
        display_name=display_name if isinstance(display_name, str) else "",
        beyin_enabled=beyin_enabled and config.get("beyin") is not False,
        read_only=read_only or config.get("read_only") is True,
        language=resolve_language(language, config),
    )
