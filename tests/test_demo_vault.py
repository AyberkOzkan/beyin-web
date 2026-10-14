from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path

from beyin_web.vault.scan import MarkdownSource
from scripts.make_demo_vault import build

TODAY = date(2026, 10, 14)


def frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    return json.loads(text[3:text.index("\n---", 3)])


class DemoVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = self.root / "Beyin"
        self.count = build(self.vault, TODAY, None)

    def test_shape_of_the_vault(self) -> None:
        self.assertEqual(self.count, 87)
        receipts = sorted((self.vault / "receipts").glob("*.md"))
        self.assertEqual(len(receipts), 87)
        days = Counter(str(frontmatter(path)["created_at"])[:10] for path in receipts)
        self.assertEqual(days["2026-10-10"], 21)
        self.assertEqual(min(days), "2026-09-28")
        statuses = Counter(frontmatter(path)["status"] for path in (self.vault / "tasks").glob("*.md"))
        self.assertEqual(statuses, {"done": 7, "active": 4, "waiting": 1, "inbox": 1})
        self.assertEqual(len(list((self.vault / "knowledge" / "concepts").glob("*.md"))), 20)
        # Without --beyin-from nothing of Beyin's program, and never a state pin, is written.
        self.assertFalse((self.vault / "beyin.py").exists())
        self.assertFalse((self.vault / ".beyin-runtime.json").exists())

    def test_the_interface_reads_every_note(self) -> None:
        snapshot = MarkdownSource(self.vault).snapshot()
        self.assertEqual(snapshot.warnings, ())
        self.assertGreater(len(snapshot.records), 150)
        self.assertEqual(snapshot.hidden_private, 1)

    def test_same_day_same_vault(self) -> None:
        again = self.root / "again"
        build(again, TODAY, None)
        files = sorted(path.relative_to(self.vault) for path in self.vault.rglob("*") if path.is_file())
        self.assertEqual(files, sorted(path.relative_to(again) for path in again.rglob("*") if path.is_file()))
        for name in files:
            self.assertEqual((self.vault / name).read_bytes(), (again / name).read_bytes(), name)


if __name__ == "__main__":
    unittest.main()
