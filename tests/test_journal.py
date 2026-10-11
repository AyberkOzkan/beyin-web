from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from beyin_web.domain.journal import day, heatmap, month
from beyin_web.vault.records import classify, make_rid
from beyin_web.vault.scan import MarkdownSource
from tests.support import make_vault


class JournalTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.snapshot = MarkdownSource(make_vault(Path(temporary.name))).snapshot()
        self.receipts = [
            SimpleNamespace(rid=record.rid,
                            created_at=datetime.fromisoformat(str(record.meta["created_at"])),
                            ref_rids=())
            for record in sorted(self.snapshot.records.values(), key=lambda record: record.path)
            if classify(record) == "receipt"
        ]
        self.tz = timezone(timedelta(hours=3))

    def test_receipt_day_uses_requested_timezone_and_chronological_order(self) -> None:
        r1, r2, r3, *_ = self.receipts
        local = day(date(2026, 1, 5), reversed(self.receipts), [], self.snapshot, self.tz)
        utc = day(date(2026, 1, 5), reversed(self.receipts), [], self.snapshot, timezone.utc)
        self.assertEqual(local["receipts"], [r1, r2])
        self.assertEqual(utc["receipts"], [r1, r2, r3])
        self.assertEqual(day(date(2026, 1, 6), self.receipts, [], self.snapshot, self.tz)["receipts"], [r3])

    def test_cards_need_only_a_date_and_keep_input_order(self) -> None:
        cards = [SimpleNamespace(date=date(2026, 1, 5)),
                 SimpleNamespace(date="2026-01-06"), SimpleNamespace(date="2026-01-05")]
        result = day(date(2026, 1, 5), self.receipts, cards, self.snapshot, self.tz)
        self.assertEqual(result["cards"], [cards[0], cards[2]])
        self.assertEqual(result["date"], "2026-01-05")

    def test_changed_records_exclude_receipts_indexes_memory_and_rejected(self) -> None:
        for number in (1, 5, 7, 12):
            with self.subTest(day=number):
                changed = day(date(2026, 1, number), [], [], self.snapshot, self.tz)["changed"]
                self.assertTrue(all(classify(record) not in {"receipt", "index", "rejected", "memory"}
                                    for record in changed))
        changed = day(date(2026, 1, 5), [], [], self.snapshot, self.tz)["changed"]
        self.assertEqual([record.path for record in changed],
                         ["notes/atlas.md", "knowledge/concepts/kavram-bir.md"])

    def test_changed_records_use_local_mtime(self) -> None:
        rid = make_rid("notes/atlas.md")
        late = replace(self.snapshot.records[rid], mtime=datetime(2026, 1, 5, 22, 30, tzinfo=timezone.utc))
        snapshot = replace(self.snapshot, records={rid: late})
        self.assertEqual(day(date(2026, 1, 6), [], [], snapshot, self.tz)["changed"], [late])
        self.assertEqual(day(date(2026, 1, 6), [], [], snapshot, timezone.utc)["changed"], [])

    def test_month_includes_zero_days_and_all_six_receipts(self) -> None:
        local = month(2026, 1, self.receipts, self.tz)
        self.assertEqual(len(local), 31)
        self.assertEqual(sum(local.values()), 6)
        self.assertEqual({key: value for key, value in local.items() if value},
                         {"2026-01-05": 2, "2026-01-06": 1, "2026-01-07": 2, "2026-01-12": 1})
        self.assertEqual(month(2026, 1, self.receipts, timezone.utc)["2026-01-05"], 3)
        self.assertEqual(month(2026, 1, self.receipts, self.tz)["2026-01-01"], 0)
        self.assertEqual(len(month(2024, 2, [], self.tz)), 29)
        self.assertEqual(len(month(2026, 2, [], self.tz)), 28)

    def test_heatmap_has_monday_weeks_and_matches_month_counts(self) -> None:
        result = heatmap(2, date(2026, 1, 18), self.receipts, self.tz)
        self.assertEqual(list(result)[0], "2026-01-05")
        self.assertEqual(list(result)[-1], "2026-01-18")
        self.assertEqual(len(result), 14)
        self.assertEqual(sum(result.values()), 6)
        monthly = month(2026, 1, self.receipts, self.tz)
        self.assertEqual(result, {key: monthly[key] for key in result})
        self.assertEqual(heatmap(2, date(2026, 1, 18), self.receipts, timezone.utc)["2026-01-05"], 3)

    def test_heatmap_current_week_future_days_are_zero_and_bounds_work(self) -> None:
        result = heatmap(1, date(2026, 1, 5), self.receipts, self.tz)
        self.assertEqual(len(result), 7)
        self.assertEqual(result["2026-01-05"], 2)
        self.assertEqual(result["2026-01-06"], 0)
        self.assertEqual(heatmap(0, date(2026, 1, 5), self.receipts, self.tz), {})
        self.assertEqual(list(heatmap(2, date(2026, 1, 1), [], self.tz))[0], "2025-12-22")
        with self.assertRaises(ValueError):
            heatmap(-1, date(2026, 1, 5), self.receipts, self.tz)

    def test_functions_do_not_mutate_inputs_and_ties_are_deterministic(self) -> None:
        original = list(self.receipts)
        tied = [
            SimpleNamespace(rid="b", created_at=original[0].created_at),
            SimpleNamespace(rid="a", created_at=original[0].created_at),
        ]
        self.assertEqual([receipt.rid for receipt in day(date(2026, 1, 5), tied, [], self.snapshot, self.tz)["receipts"]],
                         ["a", "b"])
        month(2026, 1, self.receipts, self.tz)
        heatmap(2, date(2026, 1, 18), self.receipts, self.tz)
        self.assertEqual(self.receipts, original)

    def test_naive_timestamps_do_not_use_machine_timezone(self) -> None:
        receipts = [SimpleNamespace(rid="naive", created_at=datetime(2026, 1, 5))]
        with self.assertRaises(ValueError):
            month(2026, 1, receipts, self.tz)


if __name__ == "__main__":
    unittest.main()
