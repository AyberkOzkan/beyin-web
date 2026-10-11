"""Build obsidian://open URIs from vault-relative paths."""

from __future__ import annotations

import re
from urllib.parse import quote

_WSL_MOUNT_RE = re.compile(r"^/mnt/([a-zA-Z])(/|$)")
_WIN_DRIVE_RE = re.compile(r"^([a-zA-Z]):")


def _vault_path(vault_root: str) -> tuple[str, str]:
    root = vault_root.rstrip("/\\")

    m = _WSL_MOUNT_RE.match(root)
    if m:
        letter = m.group(1).upper()
        # Obsidian runs on Windows there, so a WSL mount is handed over as the drive path it stands for.
        remainder = root[len("/mnt/x"):]
        return letter + ":" + (remainder.replace("/", "\\") or "\\"), "\\"
    elif _WIN_DRIVE_RE.match(root) or root.startswith("\\\\"):
        win_root = root.replace("/", "\\")
        if _WIN_DRIVE_RE.match(win_root):
            win_root = win_root[0].upper() + win_root[1:]
        if len(win_root) == 2:
            win_root += "\\"
        return win_root, "\\"
    else:
        return root or "/", "/"


def obsidian_vault_uri(vault_root: str) -> str:
    root, _ = _vault_path(vault_root)
    return "obsidian://open?path=" + quote(root, safe="")


def obsidian_uri(vault_root: str, rel_path: str) -> str:
    rel = rel_path.replace("\\", "/").lstrip("/")
    segments = [s for s in rel.split("/") if s not in ("", ".")]
    if not segments or ".." in segments:
        raise ValueError(f"invalid rel_path: {rel_path!r}")
    root, separator = _vault_path(vault_root)
    abs_path = root.rstrip(separator) + separator + separator.join(segments)

    return "obsidian://open?path=" + quote(abs_path, safe="")
