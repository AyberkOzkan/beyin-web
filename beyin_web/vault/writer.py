from __future__ import annotations

import os
import secrets
import threading
from collections.abc import Callable
from pathlib import Path


class WriteConflict(Exception):
    """The file changed, vanished or cannot be written safely; nothing was written."""


class VaultWriter:
    """The only code that writes to the vault: new notes in one folder, edits to given notes,
    and moving a given note to the vault's trash folder. Nothing is ever deleted for good.

    Callers pass paths taken from a scan, never from a request. Every edit is a read, a pure
    transformation and an atomic replace, and is dropped when the file changed in between.
    """

    def __init__(self, root: Path, folder: str = "goals") -> None:
        self._root = root.resolve()
        self._folder = folder
        self._lock = threading.Lock()

    def _inside(self, path: Path) -> bool:
        try:
            return not path.is_symlink() and path.resolve().is_relative_to(self._root)
        except (OSError, RuntimeError):
            return False

    def create(self, name: str, text: str) -> str:
        """Write a new note without ever replacing one; return its vault-relative path."""
        directory = self._root / self._folder
        with self._lock:
            try:
                directory.mkdir(exist_ok=True)
            except OSError:
                raise WriteConflict("folder") from None
            if not directory.is_dir() or not self._inside(directory):
                raise WriteConflict("folder")
            for attempt in range(1, 100):
                path = directory / (f"{name}.md" if attempt == 1 else f"{name}-{attempt}.md")
                try:
                    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
                except FileExistsError:
                    continue
                except OSError:
                    raise WriteConflict("create") from None
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(text.encode("utf-8"))
                return path.relative_to(self._root).as_posix()
        raise WriteConflict("name")

    def discard(self, relative: str, check: Callable[[str], None]) -> str:
        """Move a note into the vault's ``.trash`` folder (Obsidian's own); return its new path.

        ``check`` sees the note as it is on disk now and raises to keep it where it is.
        """
        path = self._root / relative
        trash = self._root / ".trash"
        with self._lock:
            if path.suffix.lower() != ".md" or not self._inside(path) or not path.is_file():
                raise WriteConflict("path")
            try:
                text = path.read_bytes().decode("utf-8")
            except (OSError, UnicodeError):
                raise WriteConflict("read") from None
            check(text)
            try:
                trash.mkdir(exist_ok=True)
            except OSError:
                raise WriteConflict("folder") from None
            if not trash.is_dir() or not self._inside(trash):
                raise WriteConflict("folder")
            for attempt in range(1, 100):
                target = trash / (path.name if attempt == 1 else f"{path.stem}-{attempt}{path.suffix}")
                # A note already in the trash under this name is somebody's way back; never replace it.
                if target.exists() or target.is_symlink():
                    continue
                try:
                    os.rename(path, target)
                except OSError:
                    raise WriteConflict("move") from None
                return target.relative_to(self._root).as_posix()
        raise WriteConflict("name")

    def update(self, relative: str, transform: Callable[[str], str]) -> bool:
        """Apply transform to a note; return whether the file was rewritten."""
        path = self._root / relative
        with self._lock:
            if path.suffix.lower() != ".md" or not self._inside(path) or not path.is_file():
                raise WriteConflict("path")
            try:
                before = path.stat()
                data = path.read_bytes()
                text = data.decode("utf-8")
            except (OSError, UnicodeError):
                raise WriteConflict("read") from None
            changed = transform(text)
            if changed == text:
                return False
            temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
            try:
                descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(changed.encode("utf-8"))
                    stream.flush()
                    os.fsync(stream.fileno())
                after = path.stat()
                # Another program (Obsidian, an assistant) saved the note while we were working.
                if (after.st_mtime_ns, after.st_size) != (before.st_mtime_ns, before.st_size) \
                        or path.read_bytes() != data:
                    raise WriteConflict("changed")
                os.replace(temporary, path)
            except OSError:
                raise WriteConflict("write") from None
            finally:
                try:
                    temporary.unlink()
                except OSError:
                    pass
            return True
