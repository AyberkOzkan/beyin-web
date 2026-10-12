from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from beyin_web.domain.projects import build_projects
from beyin_web.domain.receipts import Receipt, build_receipts
from beyin_web.domain.reports import build_report
from beyin_web.domain.tasks import build_tasks
from beyin_web.vault.links import LinkIndex
from beyin_web.vault.records import Record
from beyin_web.vault.scan import VaultSnapshot


TZ = timezone(timedelta(hours=3))
TODAY = date(2026, 1, 12)
NOW = datetime(2026, 1, 12, 16, tzinfo=TZ)


class ReportsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = VaultSnapshot(1, NOW, Path("vault"), {}, None, 0, ())
        self.links = LinkIndex({}, {}, {})

    def record(
        self, rid: str, kind: str = "note", project: str | None = None,
        title: str | None = None, meta: dict[str, object] | None = None, role: str | None = None,
    ) -> Record:
        record = Record(rid, rid + ".md", kind, title or rid, project, "internal", NOW,
                        meta or {}, "", "", role)
        self.snapshot = replace(self.snapshot, records={**self.snapshot.records, rid: record})
        return record

    def receipt(
        self, rid: str, timestamp: str, refs: tuple[str, ...] = (), learned: str | None = None,
        projects: tuple[str, ...] = (),
    ) -> Receipt:
        self.record(rid, "receipt")
        return Receipt(rid, datetime.fromisoformat(timestamp), None, None, None, (), refs,
                       "summary", learned, projects, False)

    def report(self, receipts: list[Receipt], anchor: date = date(2026, 1, 7), today: date = TODAY) -> dict[str, object]:
        tasks = build_tasks(self.snapshot)
        projects = build_projects(self.snapshot, tasks, receipts, NOW)
        return build_report(self.snapshot, self.links, tasks, receipts, projects, anchor, today, TZ)

    def test_week_boundary_uses_journal_local_day_rule(self) -> None:
        receipt = self.receipt("boundary", "2026-01-11T22:30:00+00:00", learned="Monday")
        previous = self.report([receipt])
        current = self.report([receipt], TODAY)
        self.assertEqual(previous["week"]["receipts"], 0)
        self.assertEqual(current["week"]["days"]["2026-01-12"], 1)
        self.assertEqual(current["learned"][0]["day"], "2026-01-12")
        self.assertEqual(current["learned"][0]["time"], "2026-01-12T01:30:00+03:00")
        utc = build_report(self.snapshot, self.links, [], [receipt], [], TODAY, TODAY, timezone.utc)
        self.assertEqual(utc["week"]["receipts"], 0)
        self.assertEqual(utc["week"]["previous_receipts"], 1)
        with self.assertRaises(ValueError):
            self.report([replace(receipt, created_at=datetime(2026, 1, 12))])

    def test_period_totals_previous_periods_zero_days_and_bounds(self) -> None:
        receipts = [self.receipt("previous-month", "2025-12-01T10:00:00+03:00"),
                    self.receipt("previous-week", "2026-01-04T10:00:00+03:00"),
                    self.receipt("first", "2026-01-05T10:00:00+03:00", learned="one"),
                    self.receipt("second", "2026-01-05T12:00:00+03:00"),
                    self.receipt("third", "2026-01-11T23:00:00+03:00", learned="two"),
                    self.receipt("outside", "2026-01-12T10:00:00+03:00")]
        result = self.report(receipts)
        week, month = result["week"], result["month"]
        self.assertEqual((week["receipts"], week["previous_receipts"], week["active_days"], week["learned_count"]), (3, 1, 2, 2))
        self.assertEqual(list(week["days"]), [f"2026-01-{number:02}" for number in range(5, 12)])
        self.assertEqual(list(week["days"].values()), [2, 0, 0, 0, 0, 0, 1])
        self.assertEqual((month["start"], month["end"]), ("2025-12-13", "2026-01-11"))
        self.assertEqual((month["receipts"], month["previous_receipts"], month["active_days"], month["learned_count"]), (4, 1, 3, 2))
        self.assertEqual(len(month["days"]), 30)
        self.assertEqual(list(month["days"]), sorted(month["days"]))
        current = self.report(receipts, TODAY)["month"]
        self.assertEqual((current["start"], current["end"]), ("2025-12-14", "2026-01-12"))
        self.assertEqual(len(current["days"]), 30)
        self.assertEqual(current["receipts"], 5)

    def test_worked_notes_are_distinct_refs_and_do_not_use_mtime(self) -> None:
        self.record("note")
        self.record("memory", role="core")
        self.record("index", meta={"generated": True})
        self.record("task", "task")
        self.record("unused")
        receipts = [self.receipt("one", "2026-01-05T10:00:00+03:00", ("note", "memory", "index", "task")),
                    self.receipt("two", "2026-01-06T10:00:00+03:00", ("note", "missing"))]
        self.assertEqual(self.report(receipts)["week"]["worked_notes"], 2)
        self.snapshot = replace(self.snapshot, records={rid: replace(record, mtime=NOW + timedelta(days=100))
                                                       for rid, record in self.snapshot.records.items()})
        self.assertEqual(self.report(receipts)["week"]["worked_notes"], 2)

    def test_learned_content_order_ties_and_parser_omits_yok(self) -> None:
        one = self.receipt("z", "2026-01-05T12:00:00+03:00", learned="Later", projects=("alpha",))
        two = self.receipt("a", "2026-01-05T08:00:00+00:00", learned="Earlier")
        three = self.receipt("b", "2026-01-05T11:00:00+03:00", learned="Same time")
        learned = self.report([one, three, two])["learned"]
        self.assertEqual([item["rid"] for item in learned], ["a", "b", "z"])
        self.assertEqual(learned[-1], {"rid": "z", "time": "2026-01-05T12:00:00+03:00", "day": "2026-01-05",
                                      "text": "Later", "projects": ("alpha",)})
        record = self.record("yok", "receipt", meta={"created_at": "2026-01-05T12:00:00+03:00"})
        self.snapshot = replace(self.snapshot, records={**self.snapshot.records, "yok": replace(record, body="Summary\nÖğrenilen: yok\n")})
        parsed, _ = build_receipts(self.snapshot, ())
        self.assertIsNone(parsed[0].learned)
        self.assertEqual(self.report(list(parsed))["learned"], [])

    def test_projects_progress_open_tasks_period_counts_and_sort(self) -> None:
        for name in ("beta", "alpha", "quiet"):
            self.record(name, project=name)
        quiet = self.snapshot.records["quiet"]
        self.snapshot = replace(self.snapshot, records={**self.snapshot.records, "quiet": replace(quiet, mtime=NOW - timedelta(days=60))})
        for rid, status in (("done", "done"), ("active", "active"), ("waiting", "waiting"), ("cancelled", "cancelled")):
            self.record(rid, "task", "alpha", meta={"status": status})
        receipts = [self.receipt("old", "2025-12-20T12:00:00+03:00", projects=("beta",)),
                    self.receipt("new", "2026-01-05T12:00:00+03:00", projects=("beta", "alpha")),
                    self.receipt("another", "2026-01-06T12:00:00+03:00", projects=("alpha",))]
        rows = self.report(receipts)["projects"]
        self.assertEqual([item["name"] for item in rows], ["alpha", "beta", "quiet"])
        self.assertEqual(rows[0], {"name": "alpha", "title": "alpha", "done": 1, "total": 3, "quiet": False,
                                   "open_tasks": 2, "week_receipts": 2, "month_receipts": 2})
        self.assertEqual((rows[1]["week_receipts"], rows[1]["month_receipts"]), (1, 2))
        self.assertTrue(rows[2]["quiet"])

    def test_knowledge_classification_distribution_and_resolved_links(self) -> None:
        self.record("a", project="alpha")
        self.record("a-fact", "fact", "alpha")
        self.record("b", project="beta")
        self.record("c", project="charlie")
        for index in range(3):
            self.record(f"general-{index}")
        self.record("task", "task", "alpha")
        self.record("memory", project="alpha", role="core")
        self.record("index", "receipt-index", "alpha")
        self.record("rejected", "inference", "alpha", meta={"validity": "rejected"})
        receipt = self.receipt("receipt", "2026-01-05T12:00:00+03:00")
        self.links = LinkIndex({"a": ("a-fact", "b"), "b": ("a",)}, {}, {"c": ("missing",)})
        result = self.report([receipt])["knowledge"]
        self.assertEqual(result["counts"], {"notes": 6, "knowledge": 1, "tasks": 1, "receipts": 1, "links": 3})
        self.assertEqual(result["by_project"], [
            {"project": "alpha", "notes": 1, "knowledge": 1}, {"project": "beta", "notes": 1, "knowledge": 0},
            {"project": "charlie", "notes": 1, "knowledge": 0}, {"project": None, "notes": 3, "knowledge": 0}])

    def test_most_worked_counts_receipts_limits_five_and_breaks_ties_by_title_path(self) -> None:
        for rid, title in (("b-path", "Same"), ("a-path", "Same"), ("c", "C"), ("d", "D"), ("e", "E"), ("f", "F")):
            self.record(rid, title=title)
        self.record("memory", role="core")
        self.record("index", meta={"generated": True})
        receipts = [self.receipt("one", "2026-01-05T12:00:00+03:00", tuple(self.snapshot.records)),
                    self.receipt("two", "2026-01-06T12:00:00+03:00", ("b-path", "a-path", "a-path")),
                    self.receipt("outside", "2025-12-01T12:00:00+03:00", ("f",))]
        self.assertEqual(self.report(receipts)["knowledge"]["most_worked"], [
            {"rid": "a-path", "receipts": 2}, {"rid": "b-path", "receipts": 2},
            {"rid": "c", "receipts": 1}, {"rid": "d", "receipts": 1}, {"rid": "e", "receipts": 1}])

    def test_empty_inputs_and_iterables(self) -> None:
        empty = build_report(self.snapshot, self.links, iter(()), iter(()), iter(()), TODAY, TODAY, TZ)
        self.assertEqual(empty["learned"], [])
        self.assertEqual(empty["projects"], [])
        self.assertEqual(empty["knowledge"]["most_worked"], [])
        self.assertEqual(sum(empty["week"]["days"].values()), 0)
        self.assertEqual(len(empty["month"]["days"]), 30)


if __name__ == "__main__":
    unittest.main()
