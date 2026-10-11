from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from beyin_web.vault.links import build_links
from beyin_web.vault.scan import MarkdownSource
from scripts.sentetik_vault import generate_vault


class SyntheticVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def contents(self, target: Path) -> dict[str, str]:
        return {path.name: path.read_text(encoding="utf-8") for path in target.iterdir()}

    def test_requested_count_and_scan_with_resolved_links(self) -> None:
        target = self.root / "vault"
        generate_vault(target, notes=500, seed=7)
        self.assertEqual(len(list(target.glob("*.md"))), 500)
        snapshot = MarkdownSource(target).snapshot()
        self.assertEqual(len(snapshot.records), 500)
        self.assertEqual(snapshot.warnings, ())
        links = build_links(snapshot)
        self.assertFalse(any(links.unresolved.values()))
        self.assertTrue(all(links.outgoing.get(rid) for rid in snapshot.records))
        self.assertEqual(set(self.root.iterdir()), {target})

    def test_same_seed_same_bytes_and_other_seed_changes_links(self) -> None:
        first, second, third = (self.root / name for name in ("a", "b", "c"))
        generate_vault(first, notes=20, seed=7)
        generate_vault(second, notes=20, seed=7)
        generate_vault(third, notes=20, seed=8)
        self.assertEqual(self.contents(first), self.contents(second))
        self.assertNotEqual(self.contents(first), self.contents(third))

    def test_nonempty_directory_and_file_are_refused_without_writes(self) -> None:
        target = self.root / "vault"
        target.mkdir()
        marker = target / "keep.txt"
        marker.write_text("unchanged", encoding="utf-8")
        with self.assertRaises(ValueError):
            generate_vault(target, 20)
        self.assertEqual(self.contents(target), {"keep.txt": "unchanged"})
        with self.assertRaises(ValueError):
            generate_vault(marker, 20)

    def test_empty_directory_zero_one_and_negative_counts(self) -> None:
        target = self.root / "vault"
        target.mkdir()
        generate_vault(target, 0)
        self.assertEqual(list(target.iterdir()), [])
        generate_vault(target, 1)
        self.assertEqual(len(MarkdownSource(target).snapshot().records), 1)
        with self.assertRaises(ValueError):
            generate_vault(self.root / "negative", -1)
        self.assertFalse((self.root / "negative").exists())

    def test_command_line_arguments_and_refusal(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "sentetik_vault.py"
        target = self.root / "vault"
        command = [sys.executable, str(script), str(target), "--notes", "12", "--seed", "9"]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(target.glob("*.md"))), 12)
        before = self.contents(target)
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("target must be a new or empty directory", result.stderr)
        self.assertEqual(self.contents(target), before)


if __name__ == "__main__":
    unittest.main()
