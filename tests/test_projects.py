from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from beyin_web.domain.projects import Project, build_projects
from beyin_web.domain.receipts import build_receipts
from beyin_web.domain.tasks import build_tasks
from beyin_web.vault.records import make_rid
from beyin_web.vault.scan import MarkdownSource, VaultSnapshot
from tests.support import make_vault


class ProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = make_vault(Path(temporary.name))
        self.snapshot = MarkdownSource(self.vault).snapshot()
        self.now = datetime(2026, 1, 13, tzinfo=timezone.utc)

    def projects(
        self, snapshot: VaultSnapshot | None = None, now: datetime | None = None,
    ) -> tuple[Project, ...]:
        snapshot = snapshot if snapshot is not None else self.snapshot
        names = {record.project for record in snapshot.records.values() if record.project}
        receipts, warnings = build_receipts(snapshot, names)
        self.assertEqual(warnings, ())
        return build_projects(snapshot, build_tasks(snapshot), receipts, now if now is not None else self.now)

    def test_atlas_progress_note_membership_and_activity(self) -> None:
        projects = self.projects()
        self.assertEqual(tuple(project.name for project in projects), ("atlas", "cinar"))
        atlas = projects[0]
        self.assertEqual(atlas.note_rid, make_rid("notes/atlas.md"))
        self.assertEqual(atlas.title, "Atlas")
        self.assertEqual(atlas.summary, "Atlas, Deniz'in Ocak 2026 için hazırladığı sentetik projedir.")
        self.assertEqual(atlas.task_rids, tuple(make_rid(f"tasks/atlas-a{number}.md") for number in range(1, 7)))
        self.assertEqual((atlas.done, atlas.total), (2, 5))
        self.assertEqual(atlas.knowledge_rids, (make_rid("knowledge/concepts/kavram-bir.md"),))
        self.assertEqual(atlas.receipt_rids, tuple(make_rid(f"receipts/{number:064d}.md") for number in (3, 2, 1)))
        self.assertEqual(atlas.last_activity, datetime(2026, 1, 7, 8, tzinfo=timezone.utc))
        self.assertFalse(atlas.quiet)
        cinar = projects[1]
        self.assertEqual(cinar.title, "Çınar Projesi")
        self.assertEqual(cinar.last_activity, datetime(2026, 1, 12, 12, 0, 0, 250000, tzinfo=timezone.utc))
        self.assertEqual(cinar.receipt_rids, tuple(make_rid(f"receipts/{number:064d}.md") for number in (6, 4)))

    def test_quiet_requires_no_open_tasks_and_thirty_days(self) -> None:
        records = dict(self.snapshot.records)
        rid = make_rid("tasks/cinar-1.md")
        records[rid] = replace(records[rid], meta={**records[rid].meta, "status": "done"})
        snapshot = replace(self.snapshot, records=records)
        cinar = self.projects(snapshot)[1]
        threshold = cinar.last_activity + timedelta(days=30)
        self.assertFalse(self.projects(snapshot, threshold - timedelta(microseconds=1))[1].quiet)
        after = self.projects(snapshot, threshold)
        self.assertTrue(after[1].quiet)
        self.assertFalse(after[0].quiet)
        self.assertFalse(any(project.quiet for project in self.projects(now=threshold + timedelta(days=365))))
        for status in ("inbox", "active", "waiting", "blocked"):
            with self.subTest(status=status):
                records[rid] = replace(records[rid], meta={"status": status})
                self.assertFalse(self.projects(replace(snapshot, records=records), threshold)[1].quiet)

    def test_named_note_preferred_then_first_note_and_no_note_fallback(self) -> None:
        base = self.snapshot.records[make_rid("notes/atlas.md")]
        first = replace(base, rid="first", path="notes/a.md", title="First", excerpt="First summary")
        named = replace(base, rid="named", path="notes/ATLAS.md", title="Named", excerpt="Named summary")
        snapshot = replace(self.snapshot, records={first.rid: first, named.rid: named})
        project = self.projects(snapshot)[0]
        self.assertEqual((project.note_rid, project.title, project.summary), ("named", "Named", "Named summary"))
        other = replace(named, path="notes/z.md")
        project = self.projects(replace(snapshot, records={other.rid: other, first.rid: first}))[0]
        self.assertEqual(project.note_rid, "first")
        task = self.snapshot.records[make_rid("tasks/atlas-a1.md")]
        project = self.projects(replace(snapshot, records={task.rid: task}))[0]
        self.assertIsNone(project.note_rid)
        self.assertEqual((project.title, project.summary), ("atlas", ""))
        self.assertEqual((project.done, project.total), (1, 1))

    def test_excluded_records_do_not_create_projects_or_change_activity(self) -> None:
        records = dict(self.snapshot.records)
        for path in ("knowledge/v3/outcomes.md", "knowledge/concepts/reddedilen.md"):
            rid = make_rid(path)
            records[rid] = replace(records[rid], project="excluded", mtime=self.now + timedelta(days=365))
        task = records[make_rid("tasks/atlas-a1.md")]
        records[task.rid] = replace(task, meta={**task.meta, "generated": True})
        project_list = self.projects(replace(self.snapshot, records=records))
        self.assertEqual(tuple(project.name for project in project_list), ("atlas", "cinar"))
        atlas = project_list[0]
        self.assertEqual((atlas.done, atlas.total), (1, 4))
        self.assertNotIn(task.rid, atlas.task_rids)
        self.assertEqual(atlas.last_activity, datetime(2026, 1, 7, 8, tzinfo=timezone.utc))

    def test_receipt_activity_uses_created_at_and_cancelled_only_progress(self) -> None:
        task = self.snapshot.records[make_rid("tasks/atlas-a6.md")]
        receipt = self.snapshot.records[make_rid(f"receipts/{1:064d}.md")]
        receipt = replace(receipt, mtime=self.now + timedelta(days=365))
        project = self.projects(replace(self.snapshot, records={task.rid: task, receipt.rid: receipt}))[0]
        self.assertEqual((project.done, project.total), (0, 0))
        self.assertEqual(project.last_activity, datetime(2026, 1, 5, 8, 10, tzinfo=timezone.utc))

    def test_deterministic_outputs_and_pure_domain_functions(self) -> None:
        tasks = build_tasks(self.snapshot)
        receipts, warnings = build_receipts(self.snapshot, {"atlas", "cinar"})
        self.assertEqual(warnings, ())
        expected = build_projects(self.snapshot, tasks, receipts, self.now)
        reverse = replace(self.snapshot, records=dict(reversed(list(self.snapshot.records.items()))))
        self.assertEqual(expected, build_projects(reverse, reversed(tasks), reversed(receipts), self.now))
        with patch("pathlib.Path.open", side_effect=AssertionError("Filesystem access")), \
             patch("pathlib.Path.stat", side_effect=AssertionError("Filesystem access")), \
             patch("socket.socket", side_effect=AssertionError("Network access")):
            pure_tasks = build_tasks(self.snapshot)
            pure_receipts, pure_warnings = build_receipts(self.snapshot, {"atlas", "cinar"})
            self.assertEqual(tasks, pure_tasks)
            self.assertEqual((receipts, warnings), (pure_receipts, pure_warnings))
            self.assertEqual(expected, build_projects(self.snapshot, pure_tasks, pure_receipts, self.now))
        empty = replace(self.snapshot, records={})
        self.assertEqual(build_tasks(empty), ())
        self.assertEqual(build_receipts(empty, ()), ((), ()))
        self.assertEqual(build_projects(empty, (), (), self.now), ())


if __name__ == "__main__":
    unittest.main()
