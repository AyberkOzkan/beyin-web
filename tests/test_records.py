from __future__ import annotations

import hashlib
import tempfile
import unicodedata
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path

from beyin_web.vault.frontmatter import parse_frontmatter
from beyin_web.vault.records import Record, build_record, classify, make_rid
from tests.support import make_vault


class RecordTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = make_vault(Path(temporary.name))

    def record(self, relative: str, companion: str | None = None) -> Record:
        path = self.vault / relative
        meta, body, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        record, warning = build_record(
            relative, meta, body, datetime.fromtimestamp(path.stat().st_mtime, timezone.utc), companion,
        )
        self.assertIsNone(warning)
        self.assertIsNotNone(record)
        assert record is not None
        return record

    def test_title_fallbacks_and_project(self) -> None:
        atlas = self.record("notes/atlas.md")
        self.assertEqual(atlas.title, "Atlas")
        self.assertEqual(atlas.project, "atlas")
        self.assertEqual(atlas.visibility, "internal")
        self.assertEqual(self.record("notes/serbest.md").title, "Serbest not")
        self.assertEqual(self.record("notes/başlıksız.md").title, "başlıksız")
        relative = "notes/custom.md"
        (self.vault / relative).write_text(
            '---\ntitle: "Meta title"\nvisibility: public\n---\n# Heading\n', encoding="utf-8",
        )
        self.assertEqual(self.record(relative).title, "Meta title")
        self.assertEqual(self.record(relative).visibility, "public")

    def test_title_ignores_fenced_code(self) -> None:
        relative = "notes/code.md"
        (self.vault / relative).write_text("```md\n# Code\n```\n# Heading\n", encoding="utf-8")
        self.assertEqual(self.record(relative).title, "Heading")

    def test_excerpt_simplifies_first_paragraph(self) -> None:
        relative = "notes/excerpt.md"
        (self.vault / relative).write_text(
            "# Title\n\n## Section\n\n**Kalın** ve *ince*, __vurgu__ ve _diğer_; "
            "[[Çınar#Başlık]], [[hedef|takma ad]], [bağ](https://example.test/a(b)) "
            "ve `api_key`.\nİkinci satır.\n\nSonraki paragraf.\n", encoding="utf-8",
        )
        self.assertEqual(self.record(relative).excerpt,
                         "Kalın ve ince, vurgu ve diğer; Çınar, takma ad, bağ ve api_key. İkinci satır.")

    def test_excerpt_limit_and_empty_body(self) -> None:
        relative = "notes/long.md"
        for size in (239, 240, 241, 400):
            with self.subTest(size=size):
                (self.vault / relative).write_text("# Title\n\n" + "ç" * size, encoding="utf-8")
                excerpt = self.record(relative).excerpt
                self.assertEqual(excerpt, "ç" * size if size <= 240 else "ç" * 239 + "…")
        (self.vault / relative).write_text("# Title\n", encoding="utf-8")
        self.assertEqual(self.record(relative).excerpt, "")

    def test_classification_rows_preserve_filter_metadata(self) -> None:
        cases = (
            ("knowledge/v3/outcomes.md", "receipt-index", {"generated": True}),
            ("daily/v3/2026-01-05.md", "receipt-index", {"generated": True}),
            ("receipts/" + "0" * 63 + "1.md", "receipt", {}),
            ("tasks/atlas-a3.md", "task", {"status": "active"}),
            ("knowledge/concepts/kavram-bir.md", "fact", {}),
            ("knowledge/concepts/reddedilen.md", "inference", {"validity": "rejected"}),
            ("notes/güvenilmez.md", "untrusted", {}),
            ("notes/serbest.md", "note", {}),
        )
        for relative, kind, fields in cases:
            with self.subTest(relative=relative):
                record = self.record(relative)
                self.assertEqual(record.kind, kind)
                for key, expected in fields.items():
                    self.assertEqual(record.meta[key], expected)
        for kind, extra in (("preference", "validity: rejected"), ("note", "generated: true")):
            relative = "notes/classification.md"
            (self.vault / relative).write_text(f"---\nkind: {kind}\n{extra}\n---\nBody\n", encoding="utf-8")
            record = self.record(relative)
            self.assertEqual(record.kind, kind)
            self.assertTrue(record.meta)

    def test_private_and_invalid_visibility(self) -> None:
        for visibility in ("private", "unknown", "", None, [], {}, True):
            with self.subTest(visibility=visibility):
                record, warning = build_record(
                    "GIZLI-SIZINTI-ISARETI.md", {"visibility": visibility, "title": "GIZLI-SIZINTI-ISARETI"},
                    "GIZLI-SIZINTI-ISARETI", datetime.now(timezone.utc),
                )
                self.assertIsNone(record)
                self.assertEqual(warning, None if visibility == "private" else "invalid_visibility")
                self.assertNotIn("GIZLI-SIZINTI-ISARETI", repr((record, warning)))

    def test_classify_fixture_records(self) -> None:
        cases = (
            ("knowledge/v3/outcomes.md", "index"),
            ("receipts/" + "0" * 63 + "1.md", "receipt"),
            ("tasks/atlas-a3.md", "task"),
            ("knowledge/concepts/kavram-bir.md", "knowledge"),
            ("knowledge/concepts/reddedilen.md", "rejected"),
            ("🔮 850-Companion/Core.md", "memory"),
            ("notes/güvenilmez.md", "note"),
            ("notes/atlas.md", "note"),
        )
        for relative, expected in cases:
            with self.subTest(relative=relative):
                self.assertEqual(classify(self.record(relative, "🔮 850-Companion")), expected)

    def test_classify_precedence_and_legacy_rejection(self) -> None:
        base = self.record("🔮 850-Companion/Core.md", "🔮 850-Companion")
        cases = (
            ("task", {"generated": True}, "index"),
            ("receipt-index", {}, "index"),
            ("receipt", {"validity": "rejected"}, "receipt"),
            ("task", {"status": "rejected"}, "task"),
            ("fact", {"validity": "rejected"}, "knowledge"),
            ("inference", {"validity": "rejected"}, "rejected"),
            ("preference", {"validity": "rejected"}, "rejected"),
            ("inference", {"status": "rejected"}, "rejected"),
            ("preference", {"validity": "accepted", "status": "rejected"}, "rejected"),
            ("note", {"validity": "rejected"}, "memory"),
        )
        for kind, meta, expected in cases:
            with self.subTest(kind=kind, meta=meta):
                self.assertEqual(classify(replace(base, kind=kind, meta=meta)), expected)
        for generated in (False, 1, "true"):
            with self.subTest(generated=generated):
                self.assertEqual(classify(replace(base, kind="task", meta={"generated": generated})), "task")
        for kind in ("inference", "preference", "untrusted", "unknown"):
            with self.subTest(kind=kind):
                self.assertEqual(classify(replace(base, kind=kind, meta={}, role=None)), "note")

    def test_memory_roles(self) -> None:
        companion = "🔮 850-Companion"
        for filename, role in (
            ("Core.md", "core"), ("Soul.md", "soul"), ("Kurallar.md", "rules"),
            ("Last-Session.md", "last_session"), ("Threads.md", "threads"), ("Journal.md", "journal"),
        ):
            with self.subTest(filename=filename):
                relative = f"{companion}/{filename}"
                if not (self.vault / relative).exists():
                    (self.vault / relative).write_text("# Soul\n", encoding="utf-8")
                self.assertEqual(self.record(relative, companion).role, role)
                self.assertIsNone(self.record(relative).role)
        (self.vault / "notes" / "Core.md").write_text("# Core\n", encoding="utf-8")
        self.assertIsNone(self.record("notes/Core.md", companion).role)

    def test_rid_normalization(self) -> None:
        relative = "🔮/Çınar Projesi.md"
        expected = hashlib.sha1(relative.encode("utf-8")).hexdigest()[:12]
        for value in (relative, relative.replace("/", "\\"), unicodedata.normalize("NFD", relative)):
            with self.subTest(value=value):
                self.assertEqual(make_rid(value), expected)
                self.assertEqual(make_rid(value), make_rid(value))
        self.assertNotEqual(make_rid(relative), make_rid("notes/Çınar Projesi.md"))

    def test_metadata_is_deeply_immutable_and_detached(self) -> None:
        meta = {"title": "Title", "kind": "note", "project": "atlas", "visibility": "public",
                "tags": ["one"], "nested": {"values": [1]}}
        record, _ = build_record("notes/atlas.md", meta, "Body", datetime.now(timezone.utc))
        assert record is not None
        self.assertEqual(set(record.meta), {"tags", "nested"})
        meta["tags"].append("two")
        self.assertEqual(record.meta["tags"], ("one",))
        with self.assertRaises(TypeError):
            record.meta["new"] = "value"
        with self.assertRaises(TypeError):
            record.meta["nested"]["new"] = "value"
        with self.assertRaises(FrozenInstanceError):
            record.title = "Changed"


if __name__ == "__main__":
    unittest.main()
