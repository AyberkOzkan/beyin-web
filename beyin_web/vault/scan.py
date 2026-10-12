from __future__ import annotations

import errno
import os
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Protocol, TypeVar

from beyin_web.vault.frontmatter import declares_private, parse_frontmatter
from beyin_web.vault.records import Record, _memory_role, build_record, with_receipt_titles


_MAX_WORKERS = 8
_POOL_THRESHOLD = 8
_Input = TypeVar("_Input")
_Output = TypeVar("_Output")


def _parallel_map(function: Callable[[_Input], _Output], items: Sequence[_Input]) -> list[_Output]:
    if len(items) < _POOL_THRESHOLD or _MAX_WORKERS < 2:
        return [function(item) for item in items]
    # Batch cheap cached stats to avoid creating one Future per file on Windows.
    batch_size = (len(items) + _MAX_WORKERS - 1) // _MAX_WORKERS
    batches = [items[start:start + batch_size] for start in range(0, len(items), batch_size)]

    def process_batch(batch: Sequence[_Input]) -> list[_Output]:
        return [function(item) for item in batch]

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        return [result for batch in executor.map(process_batch, batches) for result in batch]


def _stat_entry(entry: os.DirEntry[str]) -> os.stat_result | None:
    try:
        return entry.stat(follow_symlinks=False)
    except (OSError, RuntimeError):
        return None


class _SkippedSymlink(Exception):
    pass


@dataclass(frozen=True)
class VaultSnapshot:
    generation: int
    scanned_at: datetime
    root: Path
    records: Mapping[str, Record]
    companion_dir: str | None
    hidden_private: int
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", MappingProxyType(dict(self.records)))
        object.__setattr__(self, "warnings", tuple(self.warnings))


class VaultSource(Protocol):
    def snapshot(self) -> VaultSnapshot: ...


@dataclass(frozen=True)
class _CachedFile:
    signature: tuple[str, int, int]
    record: Record | None
    hidden: bool
    warnings: tuple[str, ...]


class MarkdownSource:
    def __init__(
        self, root: Path, companion_dir: str | None = None, min_interval: float = 2.0,
    ) -> None:
        self._root = root.resolve()
        self._companion_dir = companion_dir
        self._min_interval = min_interval
        self._check_interval = min_interval
        self._lock = threading.Lock()
        self._last_check: float | None = None
        self._snapshot: VaultSnapshot | None = None
        self._cache: dict[str, _CachedFile] = {}

    def _walk(self) -> tuple[dict[str, tuple[Path, os.stat_result]], tuple[str, ...]]:
        files: dict[str, tuple[Path, os.stat_result]] = {}
        warnings: list[str] = []
        candidates: list[tuple[str, Path, os.DirEntry[str]]] = []
        pending = [self._root]
        visited: set[Path] = set()
        while pending:
            directory = pending.pop()
            try:
                resolved = directory.resolve()
                if not resolved.is_relative_to(self._root) or resolved in visited:
                    continue
                visited.add(resolved)
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if entry.name.startswith(".") or entry.name == "node_modules":
                            continue
                        try:
                            if entry.is_symlink():
                                continue
                            path = Path(entry.path)
                            if entry.is_dir(follow_symlinks=False):
                                pending.append(path)
                                continue
                            if path.suffix.lower() != ".md" or not entry.is_file(follow_symlinks=False):
                                continue
                            relative = path.relative_to(self._root).as_posix()
                            if directory == self._root and entry.name in {"AGENTS.md", "CLAUDE.md", "GEMINI.md"}:
                                continue
                            candidates.append((relative, path, entry))
                        except (OSError, RuntimeError):
                            warnings.append("walk_error")
            except (OSError, RuntimeError):
                warnings.append("walk_error")
        candidates.sort(key=lambda item: item[0])
        stats = _parallel_map(_stat_entry, [entry for _, _, entry in candidates])
        for (relative, path, _), stat in zip(candidates, stats):
            if stat is None:
                warnings.append("walk_error")
            elif stat.st_size:
                files[relative] = (path, stat)
        return files, tuple(sorted(warnings))

    def _find_companion(self, files: Mapping[str, object]) -> str | None:
        if self._companion_dir is not None:
            return PurePosixPath(self._companion_dir.replace("\\", "/")).as_posix()
        names = set(files)
        for relative in sorted(names):
            path = PurePosixPath(relative)
            if path.name == "Core.md" and (path.parent / "Last-Session.md").as_posix() in names:
                return path.parent.as_posix()
        return None

    def _read_file(self, path: Path) -> str:
        # Recheck at open time without resolving every ancestor for each file.
        if not hasattr(os, "O_NOFOLLOW"):
            if path.is_symlink():
                raise _SkippedSymlink
            return path.read_text(encoding="utf-8", errors="replace")
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as error:
            if error.errno == errno.ELOOP:
                raise _SkippedSymlink from None
            raise
        try:
            stream = os.fdopen(descriptor, encoding="utf-8", errors="replace")
        except BaseException:
            os.close(descriptor)
            raise
        with stream:
            return stream.read()

    def _load(
        self, relative: str, path: Path, stat: os.stat_result, companion: str | None,
    ) -> _CachedFile:
        signature = (relative, stat.st_mtime_ns, stat.st_size)
        try:
            text = self._read_file(path)
        except _SkippedSymlink:
            return _CachedFile(signature, None, False, ())
        except OSError:
            return _CachedFile(signature, None, False, ("unreadable",))
        meta, body, parse_warning = parse_frontmatter(text)
        if parse_warning and "visibility" not in meta and declares_private(text):
            return _CachedFile(signature, None, True, ())
        record, record_warning = build_record(
            relative, meta, body, datetime.fromtimestamp(stat.st_mtime, timezone.utc), companion,
        )
        if record is None:
            # Keep only a count and a generic diagnostic for hidden files.
            warnings = (record_warning,) if record_warning else ()
            return _CachedFile(signature, None, True, warnings)
        warnings = tuple(warning for warning in (
            f"{parse_warning}: {relative}" if parse_warning else None,
            f"invalid_utf8: {relative}" if "\ufffd" in text else None,
        ) if warning is not None)
        return _CachedFile(signature, record, False, warnings)

    def snapshot(self) -> VaultSnapshot:
        with self._lock:
            now = time.monotonic()
            if self._snapshot is not None and self._last_check is not None:
                if now - self._last_check < self._check_interval:
                    return self._snapshot
            had_snapshot = self._snapshot is not None
            files, walk_warnings = self._walk()
            companion = self._find_companion(files)
            cache: dict[str, _CachedFile] = {}
            to_load: list[tuple[str, Path, os.stat_result]] = []
            for relative, (path, stat) in sorted(files.items()):
                cached = self._cache.get(relative)
                signature = (relative, stat.st_mtime_ns, stat.st_size)
                if cached is None or cached.signature != signature:
                    to_load.append((relative, path, stat))
                    continue
                elif cached.record is not None:
                    role = _memory_role(relative, companion)
                    if role != cached.record.role:
                        cached = replace(cached, record=replace(cached.record, role=role))
                cache[relative] = cached
            loaded = _parallel_map(lambda item: self._load(*item, companion), to_load)
            cache.update((item[0], cached) for item, cached in zip(to_load, loaded))
            cache = dict(sorted(cache.items()))
            warnings = walk_warnings + tuple(
                warning for cached in cache.values() for warning in cached.warnings
            )
            changed = (
                self._snapshot is None or cache != self._cache
                or companion != self._snapshot.companion_dir
                or warnings != self._snapshot.warnings
            )
            self._cache = cache
            if changed:
                generation = self._snapshot.generation + 1 if self._snapshot else 1
                self._snapshot = VaultSnapshot(
                    generation=generation, scanned_at=datetime.now(timezone.utc), root=self._root,
                    # Project names are only known once every record is read; receipt titles drop them here.
                    records=with_receipt_titles({
                        cached.record.rid: cached.record for cached in cache.values() if cached.record is not None}),
                    companion_dir=companion, hidden_private=sum(cached.hidden for cached in cache.values()),
                    warnings=warnings,
                )
            self._last_check = time.monotonic()
            if had_snapshot and self._min_interval != 0:
                duration = self._last_check - now
                self._check_interval = min(30, max(self._min_interval, 10 * duration))
            assert self._snapshot is not None
            return self._snapshot
