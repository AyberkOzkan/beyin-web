from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from beyin_web import __version__


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="beyin-web")
    parser.add_argument("--vault", type=Path)
    parser.add_argument("--port", type=int, default=7373)
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--idle-exit", type=int, metavar="DAKİKA")
    parser.add_argument("--no-token", action="store_true")
    parser.add_argument(
        "--version", action="version", version=f"beyin-web {__version__}"
    )
    return parser.parse_args(argv)


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


def main(argv: Sequence[str] | None = None) -> int:
    parse_args(argv)
    print("sunucu henüz uygulanmadı", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
