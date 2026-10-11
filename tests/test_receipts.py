from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from beyin_web.domain.receipts import build_receipts
from beyin_web.vault.records import make_rid, receipt_summary, receipt_title
from beyin_web.vault.scan import MarkdownSource
from tests.support import make_vault


class ReceiptTests(unittest.TestCase):
    def test_shared_summary_keeps_markdown_and_excludes_learned_from_title(self) -> None:
        body = "\ufeffATLAS: **Not** hazırlandı.\r\nÖğrenilen: Yeni bilgi\r\nDevam.\r\nÖĞRENİLEN: yok\r\n"
        self.assertEqual(receipt_summary(body), ("ATLAS: **Not** hazırlandı.\nDevam.", "Yeni bilgi"))
        self.assertEqual(receipt_title(body, "receipts/abcdef0123456789.md", {"atlas"}), "Not hazırlandı")
        self.assertEqual(receipt_summary("Öğrenilen: yok\n"), ("", None))

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = make_vault(Path(temporary.name))
        self.snapshot = MarkdownSource(self.vault).snapshot()
        self.rids = {number: make_rid(f"receipts/{number:064d}.md") for number in range(1, 7)}

    def test_fixture_receipts_learned_and_metadata(self) -> None:
        receipts, warnings = build_receipts(self.snapshot, {"atlas", "cinar"})
        self.assertEqual(warnings, ())
        self.assertEqual(tuple(receipt.rid for receipt in receipts), tuple(self.rids[number] for number in range(6, 0, -1)))
        by_rid = {receipt.rid: receipt for receipt in receipts}
        first, second, third = (by_rid[self.rids[number]] for number in (1, 2, 3))
        self.assertEqual(first.summary, "atlas: Temel not hazırlandı.")
        self.assertIsNone(first.learned)
        self.assertEqual(second.summary, "atlas: Kavram bir ve proje notu birlikte incelendi.")
        self.assertEqual(second.learned, "Küçük adımların sonuçları ayrı ayrı izlenebilir.")
        self.assertEqual(third.summary, "atlas: Akşam değerlendirmesi tamamlandı.")
        self.assertIsNone(third.learned)
        self.assertEqual(second.event_id, f"{2:064d}")
        self.assertEqual(second.harness, "codex")
        self.assertEqual(second.refs, ("knowledge/concepts/kavram-bir.md", "notes/atlas.md"))
        self.assertEqual(second.ref_rids, tuple(make_rid(path) for path in second.refs))
        self.assertEqual(second.projects, ("atlas",))
        self.assertFalse(second.project_inferred)
        self.assertIsNone(first.session)
        sixth = by_rid[self.rids[6]]
        self.assertEqual(sixth.session, "session-cinar-20260112")
        self.assertEqual(sixth.created_at, datetime(2026, 1, 12, 12, 0, 0, 250000, tzinfo=timezone.utc))
        self.assertEqual(sixth.projects, ("cinar",))
        for receipt in receipts:
            self.assertIsNotNone(receipt.created_at.utcoffset())
            self.assertNotIn("Öğrenilen:", receipt.summary)

    def test_memory_refs_do_not_assign_projects(self) -> None:
        records = dict(self.snapshot.records)
        for path in ("🔮 850-Companion/Last-Session.md", "🔮 850-Companion/Threads.md"):
            rid = make_rid(path)
            records[rid] = replace(records[rid], project="atlas")
        receipts, _ = build_receipts(replace(self.snapshot, records=records), {"atlas", "cinar"})
        by_rid = {receipt.rid: receipt for receipt in receipts}
        fourth, fifth = by_rid[self.rids[4]], by_rid[self.rids[5]]
        self.assertEqual(fourth.projects, ("cinar",))
        self.assertTrue(fourth.project_inferred)
        self.assertEqual(fourth.ref_rids, (make_rid("🔮 850-Companion/Last-Session.md"),))
        self.assertEqual(fifth.projects, ())
        self.assertFalse(fifth.project_inferred)
        without_known_projects, _ = build_receipts(self.snapshot, ())
        fourth = next(receipt for receipt in without_known_projects if receipt.rid == self.rids[4])
        self.assertEqual(fourth.projects, ())
        self.assertFalse(fourth.project_inferred)

    def test_refs_win_over_prefix_and_deduplicate_projects(self) -> None:
        base = self.snapshot.records[self.rids[1]]
        refs = ("notes/Çınar Projesi.md", "notes/atlas.md", "notes/atlas.md", "notes/gizli.md", "notes/missing.md")
        record = replace(base, meta={**base.meta, "refs": refs}, body="unrelated: Summary\nÖğrenilen: yok\n")
        records = {**self.snapshot.records, record.rid: record}
        receipts, _ = build_receipts(replace(self.snapshot, records=records), {"unrelated"})
        receipt = next(receipt for receipt in receipts if receipt.rid == record.rid)
        self.assertEqual(receipt.refs, refs)
        self.assertEqual(receipt.ref_rids, (make_rid(refs[0]), make_rid(refs[1])))
        self.assertEqual(receipt.projects, ("atlas", "cinar"))
        self.assertFalse(receipt.project_inferred)

    def test_prefix_case_bom_crlf_and_summary_line_removal(self) -> None:
        base = self.snapshot.records[self.rids[1]]
        record = replace(base, meta={**base.meta, "refs": ()},
                         body="\ufeffÇINAR: Başlangıç\r\nÖğrenilen: Yeni bilgi\r\n\r\nSonuç.\r\n")
        receipts, _ = build_receipts(replace(self.snapshot, records={record.rid: record}), {"Çınar"})
        receipt = receipts[0]
        self.assertEqual(receipt.projects, ("Çınar",))
        self.assertTrue(receipt.project_inferred)
        self.assertEqual(receipt.summary, "ÇINAR: Başlangıç\n\nSonuç.")
        self.assertEqual(receipt.learned, "Yeni bilgi")

    def test_bad_missing_and_naive_dates_are_skipped_with_warnings(self) -> None:
        base = self.snapshot.records[self.rids[1]]
        for value in (None, "not-a-date", "2026-01-01", "2026-01-01T12:00:00", "2026-02-30T00:00:00Z", 123, []):
            with self.subTest(value=value):
                record = replace(base, meta={**base.meta, "created_at": value})
                snapshot = replace(self.snapshot, records={record.rid: record})
                before = snapshot.warnings
                receipts, warnings = build_receipts(snapshot, {"atlas"})
                self.assertEqual(receipts, ())
                self.assertEqual(warnings, (f"invalid_created_at: {record.path}",))
                self.assertEqual(snapshot.warnings, before)
        record = replace(base, meta={**base.meta, "created_at": "2026-01-01T12:00:00+03:00"})
        receipts, warnings = build_receipts(replace(self.snapshot, records={record.rid: record}), ())
        self.assertEqual(warnings, ())
        self.assertEqual(receipts[0].created_at.utcoffset().total_seconds(), 10800)

    def test_generated_receipts_and_excluded_refs(self) -> None:
        records = dict(self.snapshot.records)
        base = records[self.rids[1]]
        records[self.rids[1]] = replace(base, meta={**base.meta, "generated": True})
        rejected_rid = make_rid("knowledge/concepts/reddedilen.md")
        records[rejected_rid] = replace(records[rejected_rid], project="discarded")
        second = records[self.rids[2]]
        refs = ("knowledge/concepts/reddedilen.md", "knowledge/v3/outcomes.md")
        records[second.rid] = replace(second, meta={**second.meta, "refs": refs}, body="No project")
        receipts, _ = build_receipts(replace(self.snapshot, records=records), {"discarded"})
        self.assertNotIn(self.rids[1], {receipt.rid for receipt in receipts})
        receipt = next(receipt for receipt in receipts if receipt.rid == second.rid)
        self.assertEqual(receipt.refs, refs)
        self.assertEqual(receipt.ref_rids, ())
        self.assertEqual(receipt.projects, ())

    def test_deterministic_order_including_timestamp_ties_and_warnings(self) -> None:
        records = dict(self.snapshot.records)
        for number in (1, 2):
            record = records[self.rids[number]]
            records[record.rid] = replace(record, meta={**record.meta, "created_at": "2026-01-01T00:00:00Z"})
        for number in (3, 4):
            record = records[self.rids[number]]
            records[record.rid] = replace(record, meta={})
        snapshot = replace(self.snapshot, records=records)
        first = build_receipts(snapshot, ["atlas", "cinar"])
        second = build_receipts(replace(snapshot, records=dict(reversed(list(records.items())))), ["cinar", "atlas"])
        self.assertEqual(first, second)
        self.assertEqual(tuple(receipt.rid for receipt in first[0][-2:]), (self.rids[1], self.rids[2]))


if __name__ == "__main__":
    unittest.main()
