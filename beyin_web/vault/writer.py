from __future__ import annotations

import os
import secrets
import threading
from collections.abc import Callable
from pathlib import Path


TRASH = ".trash"
MAX_TRASHED = 500
MAX_TRASHED_BYTES = 1_000_000


class WriteConflict(Exception):
    """The file changed, vanished or cannot be written safely; nothing was written."""


class VaultWriter:
    """The only code that writes to the vault: new notes in one folder, edits to given notes,
    moving a given note to the vault's trash folder and back, and removing a note from the trash.
    Only that last step deletes anything, and only what the caller's check lets through.

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
        with self._lock:
            path = self._root / relative
            self._checked(path, check)
            return self._move(path, self._root / TRASH)

    def trashed(self) -> list[tuple[str, str]]:
        """Names and texts of the notes lying in the trash folder; what cannot be read is left out."""
        trash = self._root / TRASH
        notes: list[tuple[str, str]] = []
        with self._lock:
            if not trash.is_dir() or not self._inside(trash):
                return notes
            try:
                entries = sorted(trash.iterdir(), key=lambda entry: entry.name)
            except OSError:
                return notes
            for path in entries[:MAX_TRASHED]:
                try:
                    if path.suffix.lower() != ".md" or path.is_symlink() or not path.is_file():
                        continue
                    if path.stat().st_size <= MAX_TRASHED_BYTES:
                        notes.append((path.name, path.read_bytes().decode("utf-8")))
                except (OSError, UnicodeError):
                    continue
        return notes

    def restore(self, name: str, check: Callable[[str], None]) -> str:
        """Move a note from the trash back into the notes folder; return its new path."""
        with self._lock:
            path = self._trashed(name)
            self._checked(path, check)
            return self._move(path, self._root / self._folder)

    def purge(self, name: str, check: Callable[[str], None]) -> None:
        """Delete a note from the trash for good. This is the one thing here that cannot be undone."""
        with self._lock:
            path = self._trashed(name)
            self._checked(path, check)
            try:
                path.unlink()
            except OSError:
                raise WriteConflict("delete") from None

    def _trashed(self, name: str) -> Path:
        if Path(name).name != name or name in {"", ".", ".."}:
            raise WriteConflict("path")
        return self._root / TRASH / name

    def _checked(self, path: Path, check: Callable[[str], None]) -> None:
        """Let ``check`` see the note as it is on disk now; it raises to leave the note alone."""
        if path.suffix.lower() != ".md" or not self._inside(path) or not path.is_file():
            raise WriteConflict("path")
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeError):
            raise WriteConflict("read") from None
        check(text)

    def _move(self, path: Path, directory: Path) -> str:
        try:
            directory.mkdir(exist_ok=True)
        except OSError:
            raise WriteConflict("folder") from None
        if not directory.is_dir() or not self._inside(directory):
            raise WriteConflict("folder")
        for attempt in range(1, 100):
            target = directory / (path.name if attempt == 1 else f"{path.stem}-{attempt}{path.suffix}")
            # A note already there under this name is somebody else's; never replace it.
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
