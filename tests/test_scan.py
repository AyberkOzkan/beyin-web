from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from beyin_web.vault.records import make_rid
from beyin_web.vault.scan import MarkdownSource
from tests.support import has_outside_link, make_vault


class ScanTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = make_vault(Path(temporary.name))
        self.source = MarkdownSource(self.vault, min_interval=0)

    def write(self, relative: str, text: str) -> Path:
        path = self.vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def add_many_notes(self) -> list[Path]:
        return [self.write(f"many/note-{index:02d}.md", f"# Note {index}\n") for index in range(40)]

    def test_pooled_scan_matches_sequential_and_independent_sources(self) -> None:
        self.add_many_notes()
        with patch("beyin_web.vault.scan.ThreadPoolExecutor", wraps=ThreadPoolExecutor) as pool:
            pooled = self.source.snapshot()
        self.assertEqual(pool.call_count, 2)
        self.assertTrue(all(call.kwargs == {"max_workers": 8} for call in pool.call_args_list))
        with patch("beyin_web.vault.scan._MAX_WORKERS", 1), \
                patch("beyin_web.vault.scan.ThreadPoolExecutor", side_effect=AssertionError("Unexpected pool")):
            sequential = MarkdownSource(self.vault, min_interval=0).snapshot()
        independent = MarkdownSource(self.vault, min_interval=0).snapshot()
        for snapshot in (sequential, independent):
            self.assertEqual(list(pooled.records.items()), list(snapshot.records.items()))
            self.assertEqual(pooled.warnings, snapshot.warnings)
            self.assertEqual(pooled.hidden_private, snapshot.hidden_private)
            self.assertEqual(pooled.generation, snapshot.generation)

    def test_fewer_than_eight_changed_files_are_read_without_pool(self) -> None:
        self.add_many_notes()
        self.source.snapshot()
        for index in range(7):
            self.write(f"many/note-{index:02d}.md", f"# Changed note {index}\n")
        files = self.source._walk()
        with patch.object(self.source, "_walk", return_value=files), \
                patch("beyin_web.vault.scan.ThreadPoolExecutor", side_effect=AssertionError("Unexpected pool")), \
                patch.object(self.source, "_read_file", wraps=self.source._read_file) as read:
            self.source.snapshot()
        self.assertEqual(read.call_count, 7)

    def test_pooled_read_failure_is_isolated(self) -> None:
        paths = self.add_many_notes()
        original = self.source._read_file

        def read(path: Path) -> str:
            if path == paths[0]:
                raise OSError("unreadable marker")
            return original(path)

        with patch.object(self.source, "_read_file", side_effect=read):
            snapshot = self.source.snapshot()
        self.assertNotIn(make_rid("many/note-00.md"), snapshot.records)
        self.assertEqual(sum(record.path.startswith("many/") for record in snapshot.records.values()), 39)
        self.assertEqual(snapshot.warnings.count("unreadable"), 1)
        self.assertNotIn("unreadable marker", repr(snapshot))

    def test_pools_close_after_scan(self) -> None:
        self.add_many_notes()
        before = threading.active_count()
        self.source.snapshot()
        self.assertEqual(threading.active_count(), before)
        self.source.snapshot()
        self.assertEqual(threading.active_count(), before)

    def test_unexpected_pool_exception_propagates(self) -> None:
        self.add_many_notes()
        for error in (ValueError, RuntimeError):
            with self.subTest(error=error), \
                    patch.object(self.source, "_read_file", side_effect=error("unexpected")):
                with self.assertRaisesRegex(error, "unexpected"):
                    self.source.snapshot()
        with patch("beyin_web.vault.scan._stat_entry", side_effect=ValueError("unexpected")):
            with self.assertRaisesRegex(ValueError, "unexpected"):
                self.source.snapshot()

    def test_pooled_stat_failure_is_walk_error(self) -> None:
        self.add_many_notes()
        original = os.scandir

        class FailedEntry:
            def __init__(self, entry: os.DirEntry[str]) -> None:
                self.entry = entry
                self.name = entry.name
                self.path = entry.path

            def is_symlink(self) -> bool:
                return self.entry.is_symlink()

            def is_dir(self, *, follow_symlinks: bool) -> bool:
                return self.entry.is_dir(follow_symlinks=follow_symlinks)

            def is_file(self, *, follow_symlinks: bool) -> bool:
                return self.entry.is_file(follow_symlinks=follow_symlinks)

            def stat(self, *, follow_symlinks: bool) -> os.stat_result:
                raise OSError("stat marker")

        class Entries:
            def __init__(self, path: Path) -> None:
                self.entries = original(path)

            def __enter__(self) -> Iterator[os.DirEntry[str] | FailedEntry]:
                return (FailedEntry(entry) if entry.name == "note-00.md" else entry for entry in self.entries)

            def __exit__(self, *args: object) -> None:
                self.entries.close()

        with patch("beyin_web.vault.scan.os.scandir", side_effect=Entries):
            snapshot = self.source.snapshot()
        self.assertEqual(snapshot.warnings.count("walk_error"), 1)
        self.assertEqual(sum(record.path.startswith("many/") for record in snapshot.records.values()), 39)
        self.assertNotIn("stat marker", repr(snapshot))

    def test_fixture_snapshot(self) -> None:
        snapshot = self.source.snapshot()
        self.assertEqual(snapshot.generation, 1)
        self.assertEqual(snapshot.root, self.vault.resolve())
        self.assertEqual(snapshot.hidden_private, 3)
        self.assertEqual(snapshot.companion_dir, "🔮 850-Companion")
        self.assertEqual(snapshot.records[make_rid("notes/atlas.md")].title, "Atlas")
        self.assertEqual(snapshot.records[make_rid("notes/Çınar Projesi.md")].project, "cinar")
        self.assertEqual(snapshot.records[make_rid("🔮 850-Companion/Core.md")].role, "core")
        self.assertIsNotNone(snapshot.scanned_at.tzinfo)
        self.assertEqual(snapshot.warnings, ("frontmatter_unclosed: notes/bozuk.md", "invalid_visibility"))

    def test_every_exclusion(self) -> None:
        for relative in (
            ".hidden.md", ".hidden/note.md", "notes/.hidden.md", "notes/.folder/note.md",
            "node_modules/pkg/note.md", "notes/node_modules/pkg/note.md", "CLAUDE.md", "GEMINI.md",
            "notes/nonmarkdown.txt",
        ):
            self.write(relative, "EXCLUDED-MARKER")
        self.write("notes/empty.md", "")
        self.write("notes/AGENTS.md", "Nested instruction file")
        snapshot = self.source.snapshot()
        paths = {record.path for record in snapshot.records.values()}
        self.assertNotIn("AGENTS.md", paths)
        self.assertNotIn("notes/bos.md", paths)
        self.assertNotIn("notes/empty.md", paths)
        self.assertIn("notes/AGENTS.md", paths)
        self.assertNotIn("EXCLUDED-MARKER", repr(snapshot))
        self.assertFalse(any(path.startswith("node_modules/") or "/node_modules/" in path for path in paths))

    def test_outside_symbolic_link(self) -> None:
        if not has_outside_link(self.vault):
            self.skipTest("Symbolic links are unavailable on this platform")
        snapshot = self.source.snapshot()
        self.assertNotIn(make_rid("notes/dışarı.md"), snapshot.records)
        self.assertNotIn("KOK-DISI-ISARETI", repr(snapshot))
        self.assertNotIn("KOK-DISI-ISARETI", repr(snapshot.warnings))

    def test_internal_file_and_directory_links_are_not_followed(self) -> None:
        if not has_outside_link(self.vault):
            self.skipTest("Symbolic links are unavailable on this platform")
        (self.vault / "notes" / "alias.md").symlink_to(self.vault / "notes" / "atlas.md")
        (self.vault / "alias-dir").symlink_to(self.vault / "notes", target_is_directory=True)
        snapshot = self.source.snapshot()
        self.assertNotIn(make_rid("notes/alias.md"), snapshot.records)
        self.assertFalse(any(record.path.startswith("alias-dir/") for record in snapshot.records.values()))

    def test_file_replaced_by_outside_symlink_after_walk_is_skipped(self) -> None:
        if not has_outside_link(self.vault):
            self.skipTest("Symbolic links are unavailable on this platform")
        before = self.source.snapshot()
        path = self.write("notes/replaced.md", "# Before replacement\n")
        outside = self.vault.parent / "outside" / "hedef.md"
        original = self.source._walk

        def walk() -> tuple[dict[str, tuple[Path, os.stat_result]], tuple[str, ...]]:
            result = original()
            self.assertIn("notes/replaced.md", result[0])
            path.unlink()
            path.symlink_to(outside)
            return result

        with patch.object(self.source, "_walk", side_effect=walk):
            snapshot = self.source.snapshot()
        self.assertNotIn(make_rid("notes/replaced.md"), snapshot.records)
        self.assertEqual(snapshot.records, before.records)
        self.assertEqual(snapshot.warnings, before.warnings)
        self.assertEqual(snapshot.hidden_private, before.hidden_private)
        self.assertNotIn("KOK-DISI-ISARETI", repr(snapshot))
        self.assertNotIn("KOK-DISI-ISARETI", repr(self.source._cache))

    def test_resolved_outside_directory_is_rejected(self) -> None:
        outside = self.vault.parent / "outside"
        original = Path.resolve

        def resolve(path: Path, *args: object, **kwargs: object) -> Path:
            if path == self.vault / "notes":
                return outside
            return original(path, *args, **kwargs)

        with patch.object(Path, "resolve", resolve), patch("beyin_web.vault.scan.os.scandir", wraps=os.scandir) as walk:
            snapshot = self.source.snapshot()
        self.assertFalse(any(record.path.startswith("notes/") for record in snapshot.records.values()))
        self.assertNotIn(self.vault / "notes", [call.args[0] for call in walk.call_args_list])
        self.assertNotIn("KOK-DISI-ISARETI", repr(snapshot))

    def test_hidden_content_paths_and_diagnostics_do_not_leak(self) -> None:
        marker = "GIZLI-SIZINTI-ISARETI"
        private = self.write(f"notes/{marker}.md",
                             f"---\nvisibility: private\ntitle: {marker}\nparent:\n  child: value\n---\n{marker}\n")
        invalid = self.write(f"notes/{marker}-invalid.md",
                             f"---\nvisibility: unknown\ntitle: {marker}\n---\n{marker}\n")
        with patch.object(self.source, "_read_file", wraps=self.source._read_file) as read:
            first = self.source.snapshot()
            self.assertEqual(first.hidden_private, 5)
            self.assertNotIn(marker, repr(first))
            self.assertNotIn(marker, repr(first.records))
            self.assertNotIn(marker, repr(first.warnings))
            read.reset_mock()
            self.assertIs(self.source.snapshot(), first)
            read.assert_not_called()
        private.unlink()
        invalid.unlink()
        second = self.source.snapshot()
        self.assertEqual(second.hidden_private, 3)
        self.assertEqual(second.generation, first.generation + 1)
        self.assertNotIn(marker, repr(second))
        self.assertNotIn(marker, repr(self.source))

    def test_malformed_private_frontmatter_is_hidden_without_diagnostics(self) -> None:
        marker = "GIZLI-SIZINTI-ISARETI"
        cases = (
            ("unclosed", "visibility: private\n", "---\n{declaration}# Hidden title\n\n{marker}\n", "frontmatter_unclosed"),
            ("json", '"visibility": "private",\n', '---\n{{\n{declaration}"kind":,\n}}\n---\n# Hidden title\n\n{marker}\n', "frontmatter_invalid"),
            ("yaml", "visibility: private\n", "---\n{declaration}kind: note\ninvalid top-level line\n---\n# Hidden title\n\n{marker}\n", "frontmatter_invalid"),
        )
        before = self.source.snapshot()
        for name, declaration, template, _ in cases:
            self.write(f"notes/{marker}-{name}.md", template.format(declaration=declaration, marker=marker))
        private = self.source.snapshot()
        self.assertEqual(private.hidden_private, before.hidden_private + 3)
        self.assertEqual(private.warnings, before.warnings)
        self.assertEqual(set(private.records), set(before.records))
        for value in (private, private.records, private.warnings, self.source):
            self.assertNotIn(marker, repr(value))
        self.assertIs(self.source.snapshot(), private)
        for name, _, template, _ in cases:
            self.write(f"notes/{marker}-{name}.md", template.format(declaration="", marker=marker))
        public = self.source.snapshot()
        self.assertEqual(public.hidden_private, before.hidden_private)
        for name, _, _, warning in cases:
            relative = f"notes/{marker}-{name}.md"
            with self.subTest(name=name):
                self.assertIn(marker, public.records[make_rid(relative)].body)
                self.assertIn(f"{warning}: {relative}", public.warnings)

    def test_unparseable_private_value_is_hidden(self) -> None:
        marker = "GIZLI-SIZINTI-ISARETI"
        before = self.source.snapshot()
        self.write(f"notes/{marker}-quote.md", f'---\nkind: note\nvisibility: "private\n---\n# {marker}\n\n{marker}\n')
        snapshot = self.source.snapshot()
        self.assertEqual(snapshot.hidden_private, before.hidden_private + 1)
        self.assertEqual(set(snapshot.records), set(before.records))
        self.assertEqual(snapshot.warnings, before.warnings)
        self.assertNotIn(marker, repr(snapshot))

    def test_private_fallback_only_applies_when_visibility_is_missing(self) -> None:
        self.write("notes/duplicate.md", "---\nvisibility: private\nvisibility: public\nunsupported: |\n  text\n---\n# Public\n")
        snapshot = self.source.snapshot()
        self.assertEqual(snapshot.hidden_private, 3)
        self.assertEqual(snapshot.records[make_rid("notes/duplicate.md")].visibility, "public")
        self.assertIn("frontmatter_partial: notes/duplicate.md", snapshot.warnings)

    def test_partial_frontmatter_warnings_include_public_paths_only(self) -> None:
        marker = "GIZLI-SIZINTI-ISARETI"
        self.write("notes/partial.md", '---\nkind: task\nproject: atlas\nunsupported: "unclosed\n---\n# Task\n')
        self.write(f"notes/{marker}.md", f'---\nvisibility: private\nunsupported: "unclosed\n---\n{marker}\n')
        self.write(f"notes/{marker}-invalid.md", f'---\nvisibility: unknown\nunsupported: "unclosed\n---\n{marker}\n')
        self.write(f"notes/{marker}-bytes.md", f"---\nvisibility: private\n---\n{marker}")
        (self.vault / "notes" / f"{marker}-bytes.md").write_bytes(b"---\nvisibility: private\n---\n\xff")
        snapshot = self.source.snapshot()
        self.assertEqual(snapshot.hidden_private, 6)
        record = snapshot.records[make_rid("notes/partial.md")]
        self.assertEqual((record.kind, record.project), ("task", "atlas"))
        self.assertIn("frontmatter_partial: notes/partial.md", snapshot.warnings)
        self.assertEqual(snapshot.warnings.count("invalid_visibility"), 2)
        self.assertNotIn(marker, repr(snapshot))
        self.assertFalse(any(warning.startswith("invalid_utf8") for warning in snapshot.warnings))

    def test_unchanged_snapshot_is_same_object_without_reads(self) -> None:
        first = self.source.snapshot()
        with patch.object(self.source, "_read_file", side_effect=AssertionError("Unexpected read")):
            self.assertIs(self.source.snapshot(), first)
        self.assertEqual(first.scanned_at, self.source.snapshot().scanned_at)

    def test_unchanged_scan_resolves_directories_once_and_never_files(self) -> None:
        first = self.source.snapshot()
        original = Path.resolve
        resolved_paths: list[Path] = []

        def resolve(path: Path, *args: object, **kwargs: object) -> Path:
            resolved_paths.append(path)
            return original(path, *args, **kwargs)

        with patch.object(Path, "resolve", resolve), patch("beyin_web.vault.scan.os.scandir", wraps=os.scandir) as walk:
            with patch.object(self.source, "_read_file", side_effect=AssertionError("Unexpected read")):
                self.assertIs(self.source.snapshot(), first)
        self.assertGreater(len(resolved_paths), 0)
        self.assertTrue(all(path.is_dir() for path in resolved_paths))
        self.assertEqual(len(resolved_paths), len(set(resolved_paths)))
        self.assertEqual(walk.call_count, len(resolved_paths))
        self.assertEqual([call.args[0] for call in walk.call_args_list], resolved_paths)

    def test_initial_scan_resolves_only_directories_with_many_files(self) -> None:
        self.add_many_notes()
        original = Path.resolve
        resolved_paths: list[Path] = []

        def resolve(path: Path, *args: object, **kwargs: object) -> Path:
            resolved_paths.append(path)
            return original(path, *args, **kwargs)

        with patch.object(Path, "resolve", resolve), \
                patch("os.path.realpath", wraps=os.path.realpath) as realpath, \
                patch("beyin_web.vault.scan.os.scandir", wraps=os.scandir) as walk:
            self.source.snapshot()
        self.assertGreater(len(resolved_paths), 0)
        self.assertTrue(all(path.is_dir() for path in resolved_paths))
        self.assertEqual(len(resolved_paths), len(set(resolved_paths)))
        self.assertEqual([call.args[0] for call in walk.call_args_list], resolved_paths)
        self.assertTrue(all(Path(call.args[0]).is_dir() for call in realpath.call_args_list))

    def test_changed_file_only_is_read_and_old_snapshot_is_retained(self) -> None:
        first = self.source.snapshot()
        path = self.vault / "notes" / "atlas.md"
        previous = first.records[make_rid("notes/atlas.md")]
        with path.open("a", encoding="utf-8") as stream:
            stream.write("\nAdditional content.\n")
        with patch.object(self.source, "_read_file", wraps=self.source._read_file) as read:
            second = self.source.snapshot()
            read.assert_called_once_with(path)
        self.assertIsNot(first, second)
        self.assertEqual(second.generation, first.generation + 1)
        self.assertNotIn("Additional content.", previous.body)
        self.assertIn("Additional content.", second.records[previous.rid].body)
        self.assertIs(first.records[make_rid("notes/serbest.md")], second.records[make_rid("notes/serbest.md")])
        self.assertIs(self.source.snapshot(), second)

    def test_mtime_and_size_are_both_in_signature(self) -> None:
        first = self.source.snapshot()
        path = self.vault / "notes" / "atlas.md"
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        with patch.object(self.source, "_read_file", wraps=self.source._read_file) as read:
            second = self.source.snapshot()
            read.assert_called_once_with(path)
        self.assertEqual(second.generation, first.generation + 1)
        stat = path.stat()
        with path.open("a", encoding="utf-8") as stream:
            stream.write("More text")
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        with patch.object(self.source, "_read_file", wraps=self.source._read_file) as read:
            third = self.source.snapshot()
            read.assert_called_once_with(path)
        self.assertEqual(third.generation, second.generation + 1)

    def test_add_delete_and_empty_file(self) -> None:
        first = self.source.snapshot()
        path = self.write("notes/new-🧠.md", "# Yeni not\n\nYeni içerik.\n")
        second = self.source.snapshot()
        rid = make_rid("notes/new-🧠.md")
        self.assertIn(rid, second.records)
        self.assertEqual(second.generation, first.generation + 1)
        path.write_text("", encoding="utf-8")
        third = self.source.snapshot()
        self.assertNotIn(rid, third.records)
        self.assertEqual(third.generation, second.generation + 1)
        (self.vault / "notes" / "atlas.md").unlink()
        fourth = self.source.snapshot()
        self.assertNotIn(make_rid("notes/atlas.md"), fourth.records)
        self.assertEqual(fourth.generation, third.generation + 1)
        self.assertIn(make_rid("notes/atlas.md"), first.records)

    def test_minimum_interval_is_since_last_check(self) -> None:
        source = MarkdownSource(self.vault, min_interval=2)
        with patch("beyin_web.vault.scan.time.monotonic", return_value=0) as clock:
            first = source.snapshot()
            with patch.object(source, "_walk", wraps=source._walk) as walk:
                clock.return_value = 1
                self.assertIs(source.snapshot(), first)
                walk.assert_not_called()
                clock.return_value = 2
                self.assertIs(source.snapshot(), first)
                walk.assert_called_once()
                self.write("notes/later.md", "# Later\n")
                clock.return_value = 3
                self.assertIs(source.snapshot(), first)
                self.assertEqual(walk.call_count, 1)
                clock.return_value = 4
                second = source.snapshot()
                self.assertEqual(second.generation, first.generation + 1)
                self.assertEqual(walk.call_count, 2)

    def test_adaptive_interval_is_ten_times_scan_duration_capped_at_thirty(self) -> None:
        for duration, interval in ((0.5, 5), (10, 30)):
            with self.subTest(duration=duration):
                source = MarkdownSource(self.vault, min_interval=2)
                original = source._walk
                with patch("beyin_web.vault.scan.time.monotonic", return_value=0) as clock:
                    first = source.snapshot()

                    def walk() -> tuple[dict[str, tuple[Path, os.stat_result]], tuple[str, ...]]:
                        result = original()
                        clock.return_value += duration
                        return result

                    with patch.object(source, "_walk", side_effect=walk) as checked:
                        clock.return_value = 2
                        self.assertIs(source.snapshot(), first)
                        checked.assert_called_once()
                        finished = 2 + duration
                        clock.return_value = finished + interval - 1
                        self.assertIs(source.snapshot(), first)
                        self.assertEqual(checked.call_count, 1)
                        clock.return_value = finished + interval
                        self.assertIs(source.snapshot(), first)
                        self.assertEqual(checked.call_count, 2)

    def test_long_initial_scan_keeps_minimum_interval(self) -> None:
        source = MarkdownSource(self.vault, min_interval=2)
        with patch("beyin_web.vault.scan.time.monotonic", side_effect=[0, 100]):
            first = source.snapshot()
        with patch("beyin_web.vault.scan.time.monotonic", return_value=101) as clock, \
                patch.object(source, "_walk", wraps=source._walk) as walk:
            self.assertIs(source.snapshot(), first)
            walk.assert_not_called()
            clock.return_value = 102
            self.assertIs(source.snapshot(), first)
            walk.assert_called_once()

    def test_zero_interval_disables_adaptation_even_for_long_scans(self) -> None:
        original = self.source._walk
        with patch("beyin_web.vault.scan.time.monotonic", return_value=0) as clock:
            def walk() -> tuple[dict[str, tuple[Path, os.stat_result]], tuple[str, ...]]:
                result = original()
                clock.return_value += 10
                return result

            with patch.object(self.source, "_walk", side_effect=walk) as checked:
                first = self.source.snapshot()
                self.assertIs(self.source.snapshot(), first)
                self.assertIs(self.source.snapshot(), first)
                self.assertEqual(checked.call_count, 3)

    def test_companion_override_and_discovery_changes(self) -> None:
        source = MarkdownSource(self.vault, companion_dir="notes", min_interval=0)
        self.write("notes/Core.md", "# Core\n")
        first = source.snapshot()
        self.assertEqual(first.companion_dir, "notes")
        self.assertEqual(first.records[make_rid("notes/Core.md")].role, "core")
        self.assertIsNone(first.records[make_rid("🔮 850-Companion/Core.md")].role)
        first = self.source.snapshot()
        self.assertEqual(first.companion_dir, "🔮 850-Companion")
        (self.vault / "🔮 850-Companion" / "Last-Session.md").unlink()
        with patch.object(self.source, "_read_file", wraps=self.source._read_file) as read:
            second = self.source.snapshot()
            read.assert_not_called()
        self.assertIsNone(second.companion_dir)
        self.assertIsNone(second.records[make_rid("🔮 850-Companion/Core.md")].role)
        self.assertEqual(first.records[make_rid("🔮 850-Companion/Core.md")].role, "core")
        self.write("notes/Last-Session.md", "# Session\n")
        third = self.source.snapshot()
        self.assertEqual(third.companion_dir, "notes")
        self.assertEqual(third.records[make_rid("notes/Core.md")].role, "core")

    def test_corrupt_utf8_is_replaced_with_warning(self) -> None:
        path = self.vault / "notes" / "bytes.md"
        path.write_bytes(b"# Title\n\nInvalid \xff bytes\n")
        snapshot = self.source.snapshot()
        record = snapshot.records[make_rid("notes/bytes.md")]
        self.assertIn("\ufffd", record.body)
        self.assertIn("invalid_utf8: notes/bytes.md", snapshot.warnings)

    def test_read_failure_diagnostic_has_no_path_or_exception_text(self) -> None:
        original = self.source._read_file
        marker = "GIZLI-SIZINTI-ISARETI"

        def read(path: Path) -> str:
            if path.name == "gizli.md":
                raise OSError(marker)
            return original(path)

        with patch.object(self.source, "_read_file", side_effect=read):
            snapshot = self.source.snapshot()
        self.assertNotIn(marker, repr(snapshot))
        self.assertNotIn("gizli.md", repr(snapshot.warnings))
        self.assertIn("unreadable", snapshot.warnings)

    def test_walk_error_has_no_path_or_exception_text(self) -> None:
        original = os.scandir

        def scandir(path: Path) -> AbstractContextManager[Iterator[os.DirEntry[str]]]:
            if path == self.vault / "notes":
                raise OSError("GIZLI-SIZINTI-ISARETI")
            return original(path)

        with patch("beyin_web.vault.scan.os.scandir", side_effect=scandir):
            snapshot = self.source.snapshot()
        self.assertIn("walk_error", snapshot.warnings)
        self.assertNotIn("GIZLI-SIZINTI-ISARETI", repr(snapshot.warnings))
        self.assertNotIn("notes", repr(snapshot.warnings))

    def test_snapshot_and_metadata_are_immutable(self) -> None:
        snapshot = self.source.snapshot()
        with self.assertRaises(TypeError):
            snapshot.records["new"] = snapshot.records[make_rid("notes/atlas.md")]
        with self.assertRaises(FrozenInstanceError):
            snapshot.generation = 10
        record = snapshot.records[make_rid("notes/Çınar Projesi.md")]
        self.assertEqual(record.meta["participants"], ("Deniz", "Atlas"))
        with self.assertRaises(TypeError):
            record.meta["owner"] = "Other"

    def test_concurrent_snapshots_read_each_changed_file_once(self) -> None:
        with patch.object(self.source, "_read_file", wraps=self.source._read_file) as read:
            with ThreadPoolExecutor(max_workers=8) as executor:
                initial = list(executor.map(lambda _: self.source.snapshot(), range(16)))
            self.assertTrue(all(snapshot is initial[0] for snapshot in initial))
            first_read_count = read.call_count
            self.assertGreater(first_read_count, 0)
            path = self.write("notes/atlas.md", "# Changed\n\nContent.\n")
            read.reset_mock()
            with ThreadPoolExecutor(max_workers=8) as executor:
                updated = list(executor.map(lambda _: self.source.snapshot(), range(16)))
            self.assertTrue(all(snapshot is updated[0] for snapshot in updated))
            self.assertEqual(updated[0].generation, initial[0].generation + 1)
            read.assert_called_once_with(path)

    def test_measurement_script_only_reads(self) -> None:
        paths = [path for path in self.vault.rglob("*") if path.is_file() and not path.is_symlink()]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "scripts/measure.py", str(self.vault)], cwd=root,
            capture_output=True, text=True, encoding="utf-8", timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"cold_ms: \d+\.\d+")
        self.assertRegex(result.stdout, r"warm_ms: \d+\.\d+")
        self.assertIn("warnings: 2", result.stdout)
        self.assertIn("receipt: 6", result.stdout)
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths})

    def test_scanning_layer_has_no_upper_layer_imports(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for filename in ("frontmatter.py", "records.py", "scan.py"):
            tree = ast.parse((root / "beyin_web" / "vault" / filename).read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            for module in imports:
                with self.subTest(filename=filename, module=module):
                    self.assertFalse(module.startswith(("beyin_web.http", "beyin_web.domain", "beyin_web.runtime")))


if __name__ == "__main__":
    unittest.main()
