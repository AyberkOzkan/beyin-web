from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from beyin_web.domain.search import search, search_fold
from beyin_web.vault.records import Record, build_record, classify, make_rid
from beyin_web.vault.scan import MarkdownSource
from tests.support import make_vault


class SearchTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        vault = make_vault(Path(temporary.name))
        (vault / "notes" / "arama.md").write_text(
            '\ufeff---\r\nproject: atlas\r\n---\r\n# Üretim günlüğü\r\n\r\n'
            'Bu çalışma ısı ölçümü içindir. Çalışma sırasında ISI izlenir.\r\n',
            encoding="utf-8", newline="",
        )
        self.snapshot = MarkdownSource(vault).snapshot()
        self.receipts = [
            SimpleNamespace(rid=record.rid,
                            created_at=datetime.fromisoformat(str(record.meta["created_at"])),
                            ref_rids=tuple(make_rid(path) for path in record.meta["refs"]))
            for record in self.snapshot.records.values() if classify(record) == "receipt"
        ]
        self.note_rid = make_rid("notes/arama.md")

    def record(self, path: str, title: str, body: str, day: int = 1) -> Record:
        record, warning = build_record(path, {"title": title}, body,
                                       datetime(2026, 1, day, tzinfo=timezone.utc))
        self.assertIsNone(warning)
        assert record is not None
        return record

    def test_fold_is_character_wise_and_length_preserving(self) -> None:
        self.assertEqual(search_fold("İ I ı Ç ç Ş ş Ğ ğ Ö ö Ü ü"), "i i i c c s s g g o o u u")
        text = "Çalışma İSI Straße ΑΣ ẞ 🙂 i\u0307"
        folded = search_fold(text)
        self.assertEqual(len(folded), len(text))
        self.assertEqual(search_fold("ΟΣ"), "οσ")
        for original, result in zip(text, folded):
            self.assertEqual(len(search_fold(original)), 1)
            self.assertEqual(search_fold(original), result)

    def test_ascii_query_finds_turkish_word_and_original_highlights(self) -> None:
        result = search(self.snapshot, self.receipts, "calisma")
        self.assertEqual([item["rid"] for item in result], [self.note_rid])
        highlights = [result[0]["snippet"][start:end] for start, end in result[0]["highlights"]]
        self.assertEqual(highlights, ["çalışma", "Çalışma"])
        self.assertEqual(result[0]["kind"], "note")
        self.assertEqual(result[0]["project"], "atlas")

    def test_dotted_dotless_and_ascii_i_have_identical_results(self) -> None:
        expected = search(self.snapshot, self.receipts, "ısı")
        self.assertIn(self.note_rid, [item["rid"] for item in expected])
        for query in ("ISI", "İSİ", "isi", "Isı"):
            self.assertEqual(search(self.snapshot, self.receipts, query), expected)
        result = next(item for item in expected if item["rid"] == self.note_rid)
        self.assertEqual([result["snippet"][start:end] for start, end in result["highlights"]], ["ısı", "ISI"])

    def test_all_query_words_are_required_across_title_and_body(self) -> None:
        self.assertEqual([item["rid"] for item in search(self.snapshot, self.receipts, "calisma isi")], [self.note_rid])
        self.assertEqual([item["rid"] for item in search(self.snapshot, self.receipts, "uretim isi")], [self.note_rid])
        self.assertEqual(search(self.snapshot, self.receipts, "calisma eksik-sozcuk"), [])
        self.assertEqual(search(self.snapshot, self.receipts, "   \t\n "), [])
        self.assertEqual(search(self.snapshot, self.receipts, "calisma calisma"),
                         search(self.snapshot, self.receipts, "calisma"))

    def test_ranking_prefers_title_then_count_then_newest_and_stable_ties(self) -> None:
        records = [self.record("title.md", "Sinyal", "sinyal", 1),
                   self.record("many.md", "Many", "sinyal sinyal sinyal", 2),
                   self.record("old.md", "Old", "sinyal", 3),
                   self.record("new.md", "New", "sinyal", 4),
                   self.record("tie.md", "Tie", "sinyal", 4)]
        snapshot = replace(self.snapshot, records={record.rid: record for record in records})
        result = search(snapshot, [], "sinyal")
        tied = sorted([records[3].rid, records[4].rid])
        self.assertEqual([item["rid"] for item in result],
                         [records[0].rid, records[1].rid, *tied, records[2].rid])
        self.assertEqual(search(snapshot, [], "sinyal", limit=2), result[:2])
        self.assertEqual(search(snapshot, [], "sinyal", limit=0), [])
        self.assertEqual(search(snapshot, [], "sinyal", limit=-1), [])

    def test_snippet_centers_on_first_body_match_and_preserves_offsets(self) -> None:
        record = self.record("long.md", "Long", "ö" * 250 + " çalışma ısı " + "ü" * 250)
        snapshot = replace(self.snapshot, records={record.rid: record})
        result = search(snapshot, [], "calisma isi")[0]
        self.assertEqual(len(result["snippet"]), 160)
        self.assertEqual([result["snippet"][start:end] for start, end in result["highlights"]],
                         ["çalışma", "ısı"])
        self.assertIn(result["snippet"], record.body)

    def test_title_only_empty_body_and_matches_at_body_edges(self) -> None:
        for body in ("", "No body match", "sinyal" + "ç" * 200, "ç" * 200 + "sinyal"):
            with self.subTest(body=body[:10]):
                record = self.record("edges.md", "SİNYAL", body)
                snapshot = replace(self.snapshot, records={record.rid: record})
                result = search(snapshot, [], "sinyal")[0]
                self.assertEqual(len(result["highlights"]), 1)
                start, end = result["highlights"][0]
                self.assertEqual(search_fold(result["snippet"][start:end]), "sinyal")

    def test_overlapping_highlights_merge_and_long_query_is_not_truncated(self) -> None:
        record = self.record("overlap.md", "Overlap", "çalışma")
        snapshot = replace(self.snapshot, records={record.rid: record})
        result = search(snapshot, [], "calisma lisma")[0]
        self.assertEqual(result["highlights"], [[0, 7]])
        word = "ş" * 200
        record = self.record("long-word.md", "Long word", "prefix " + word + " suffix")
        result = search(replace(snapshot, records={record.rid: record}), [], "s" * 200)[0]
        start, end = result["highlights"][0]
        self.assertEqual(result["snippet"][start:end], word)

    def test_filters_summary_and_hidden_index_rejected_exclusion(self) -> None:
        self.assertEqual(search(self.snapshot, self.receipts, "calisma", kind="fact"), [])
        self.assertEqual(search(self.snapshot, self.receipts, "calisma", project="cinar"), [])
        self.assertEqual(len(search(self.snapshot, self.receipts, "calisma", kind="note", project="atlas")), 1)
        result = search(self.snapshot, self.receipts, "calisma")[0]
        self.assertEqual(set(result), {"rid", "title", "kind", "project", "path", "mtime", "excerpt", "snippet", "highlights"})
        record = self.snapshot.records[self.note_rid]
        self.assertEqual(result["mtime"], record.mtime.isoformat())
        self.assertEqual(result["excerpt"], record.excerpt)
        self.assertEqual(search(self.snapshot, self.receipts, "GIZLI-SIZINTI-ISARETI"), [])
        for record in self.snapshot.records.values():
            if classify(record) in {"index", "rejected"}:
                results = search(self.snapshot, self.receipts, record.title)
                self.assertNotIn(record.rid, {item["rid"] for item in results})

    def test_receipts_sort_by_creation_time_and_use_inferred_project_filter(self) -> None:
        records = [record for record in self.snapshot.records.values() if classify(record) == "receipt"]
        snapshot = replace(self.snapshot, records={record.rid: record for record in records})
        result = search(snapshot, self.receipts, "atlas")
        self.assertEqual([item["rid"] for item in result],
                         [make_rid("receipts/" + "0" * 63 + str(number) + ".md") for number in (3, 2, 1)])
        receipt = SimpleNamespace(rid=result[0]["rid"], created_at=self.receipts[2].created_at,
                                  ref_rids=(), projects=("atlas",))
        filtered = search(snapshot, [receipt], "atlas", kind="receipt", project="atlas")
        self.assertEqual([item["rid"] for item in filtered], [receipt.rid])

    def test_project_filter_works_with_minimal_receipts_and_classified_kind(self) -> None:
        filtered = search(self.snapshot, self.receipts, "atlas", kind="receipt", project="atlas")
        self.assertEqual(len(filtered), 3)
        self.assertEqual(search(self.snapshot, self.receipts, "kavram", kind="knowledge"),
                         search(self.snapshot, self.receipts, "kavram", kind="fact"))

    def test_input_order_does_not_change_results_and_inputs_remain_unchanged(self) -> None:
        original = repr((self.snapshot, self.receipts))
        expected = search(self.snapshot, self.receipts, "atlas")
        reordered = replace(self.snapshot, records=dict(reversed(list(self.snapshot.records.items()))))
        self.assertEqual(search(reordered, reversed(self.receipts), "atlas"), expected)
        self.assertEqual(repr((self.snapshot, self.receipts)), original)


if __name__ == "__main__":
    unittest.main()
