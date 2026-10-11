from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from beyin_web.domain.tasks import build_tasks, natural_key
from beyin_web.vault.records import make_rid
from beyin_web.vault.scan import MarkdownSource
from tests.support import make_vault


class TaskTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = make_vault(Path(temporary.name))
        self.snapshot = MarkdownSource(self.vault).snapshot()

    def test_all_fixture_statuses_and_fields(self) -> None:
        tasks = {task.id: task for task in build_tasks(self.snapshot)}
        self.assertEqual(len(tasks), 7)
        for name, status in (
            ("atlas-a1", "done"), ("atlas-a2", "done"), ("atlas-a3", "active"),
            ("atlas-a4", "waiting"), ("atlas-a5", "blocked"), ("atlas-a6", "cancelled"), ("cinar-1", "inbox"),
        ):
            with self.subTest(name=name):
                task = tasks[name]
                self.assertEqual(task.rid, make_rid(f"tasks/{name}.md"))
                self.assertEqual(task.status, status)
                self.assertEqual(task.owner, "Deniz")
                self.assertEqual(task.revision, 1)
        self.assertEqual(tasks["atlas-a3"].next_action, "İkinci örneği doğrula.")
        self.assertEqual(tasks["atlas-a4"].due_at, "2026-01-20")
        self.assertEqual(tasks["cinar-1"].review_at, "2026-01-15")
        self.assertEqual(tasks["atlas-a1"].project, "atlas")
        self.assertIsNone(tasks["atlas-a1"].next_action)
        self.assertEqual(tasks["atlas-a3"].title, "Atlas A3: Örnekleri doğrula")

    def test_checklist_counts_and_open_tilde(self) -> None:
        rid = make_rid("tasks/atlas-a3.md")
        original = next(task for task in build_tasks(self.snapshot) if task.rid == rid)
        self.assertEqual((original.checklist_done, original.checklist_total), (2, 4))
        record = replace(self.snapshot.records[rid], body="\ufeff- [x] Done\r\n- [X] Done\r\n"
                         "- [ ] Open\r\n- [~] Ongoing\r\n- [q] Invalid\r\n"
                         "```md\r\n- [x] Code\r\n```\r\n`- [x] Inline`\r\n")
        snapshot = replace(self.snapshot, records={rid: record})
        task = build_tasks(snapshot)[0]
        self.assertEqual((task.checklist_done, task.checklist_total), (2, 4))

    def test_unknown_status_and_filename_fallback(self) -> None:
        rid = make_rid("tasks/atlas-a1.md")
        record = self.snapshot.records[rid]
        for status in (None, "unexpected", [], 42):
            with self.subTest(status=status):
                altered = replace(record, meta={"status": status})
                task = build_tasks(replace(self.snapshot, records={rid: altered}))[0]
                self.assertEqual(task.id, "atlas-a1")
                self.assertEqual(task.status, "unknown")
                self.assertIsNone(task.owner)
                self.assertIsNone(task.revision)

    def test_natural_order_and_deterministic_ties(self) -> None:
        self.assertEqual(sorted(["A10", "A2", "A1"], key=natural_key), ["A1", "A2", "A10"])
        self.assertEqual(sorted(["10", "2", ""], key=natural_key), ["", "2", "10"])
        base = self.snapshot.records[make_rid("tasks/atlas-a1.md")]
        records = {
            path: replace(base, rid=path, path=path, title=title)
            for path, title in (("tasks/z.md", "A2"), ("tasks/b.md", "A10"), ("tasks/a.md", "A2"))
        }
        snapshot = replace(self.snapshot, records=records)
        tasks = build_tasks(snapshot)
        self.assertEqual(tuple(task.rid for task in tasks), ("tasks/a.md", "tasks/z.md", "tasks/b.md"))
        self.assertEqual(tasks, build_tasks(replace(snapshot, records=dict(reversed(list(records.items()))))))

    def test_generated_tasks_are_excluded(self) -> None:
        rid = make_rid("tasks/atlas-a1.md")
        record = replace(self.snapshot.records[rid], meta={"generated": True})
        self.assertEqual(build_tasks(replace(self.snapshot, records={rid: record})), ())


if __name__ == "__main__":
    unittest.main()
