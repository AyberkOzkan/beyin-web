from __future__ import annotations

import tempfile
import unicodedata
import unittest
from dataclasses import replace
from pathlib import Path

from beyin_web.vault.links import LinkIndex, build_links
from beyin_web.vault.records import make_rid
from beyin_web.vault.scan import MarkdownSource
from tests.support import make_vault


class LinkTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = make_vault(Path(temporary.name))
        self.source = MarkdownSource(self.vault, min_interval=0)

    def write(self, path: str, body: str) -> None:
        target = self.vault / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    def test_fixture_forms_and_backlinks(self) -> None:
        links = build_links(self.source.snapshot())
        atlas = make_rid("notes/atlas.md")
        expected = {
            make_rid("knowledge/concepts/kavram-bir.md"),
            make_rid("knowledge/concepts/kavram-iki.md"), make_rid("tasks/atlas-a2.md"),
        }
        self.assertEqual(set(links.outgoing[atlas]), expected)
        self.assertEqual(links.unresolved[atlas], ("gizli", "olmayan-not"))
        for target in expected:
            self.assertIn(atlas, links.incoming[target])

    def test_embed_paths_self_links_and_duplicates(self) -> None:
        self.write("notes/links.md", "\ufeff# Links\r\n"
                   "![[kavram-bir]] [[kavram-bir|alias]] [[links]] [[notes/links.md]] "
                   "[[knowledge/concepts/kavram-iki]] [[tasks/atlas-a2.md#Heading|Alias]] "
                   "[[missing|Alias]] [[missing#Heading]] [[#Local heading]]")
        links = build_links(self.source.snapshot())
        source = make_rid("notes/links.md")
        self.assertEqual(links.outgoing[source], (
            make_rid("knowledge/concepts/kavram-bir.md"),
            make_rid("knowledge/concepts/kavram-iki.md"), make_rid("tasks/atlas-a2.md"),
        ))
        self.assertEqual(links.unresolved[source], ("missing",))
        self.assertNotIn(source, links.incoming[source])

    def test_turkish_case_and_unicode_normalization(self) -> None:
        self.write("notes/turkish.md", "[[ÇINAR PROJESİ]] [[" + unicodedata.normalize("NFD", "Çınar Projesi.md") + "]]")
        self.write("notes/INBOX.md", "# Inbox")
        self.write("notes/ISI.md", "# Heat")
        self.write("notes/cases.md", "[[inbox]] [[Inbox]] [[ısı]] [[isi]] [[İSİ]]")
        links = build_links(self.source.snapshot())
        self.assertEqual(links.outgoing[make_rid("notes/turkish.md")], (make_rid("notes/Çınar Projesi.md"),))
        self.assertEqual(set(links.outgoing[make_rid("notes/cases.md")]), {
            make_rid("notes/INBOX.md"), make_rid("notes/ISI.md"),
        })
        self.assertEqual(links.unresolved[make_rid("notes/cases.md")], ())

    def test_ambiguous_names_choose_shortest_then_alphabetical(self) -> None:
        for path in ("long/path/shared.md", "b/shared.md", "a/shared.md"):
            self.write(path, "# Shared")
        self.write("notes/ambiguity.md", "[[shared]] [[long/path/shared]] [[no/path/shared.md]]")
        links = build_links(self.source.snapshot())
        source = make_rid("notes/ambiguity.md")
        self.assertEqual(links.outgoing[source], (make_rid("a/shared.md"), make_rid("long/path/shared.md")))
        self.assertEqual(links.unresolved[source], ("no/path/shared.md",))

    def test_fenced_and_inline_code(self) -> None:
        self.write("notes/code-links.md", "`[[inline]]` ``literal ` [[double]]``\n"
                   "`multi\n[[multiline]]`\n"
                   "~~~text\n[[tilde]]\n~~~\n"
                   "````md\n[[fenced]]\n```\n[[still-fenced]]\n`````\n"
                   "[[kavram-bir]] `unclosed [[olmayan-not]]\n")
        links = build_links(self.source.snapshot())
        source = make_rid("notes/code-links.md")
        self.assertEqual(links.outgoing[source], (make_rid("knowledge/concepts/kavram-bir.md"),))
        self.assertEqual(links.unresolved[source], ("olmayan-not",))

    def test_indented_lines_keep_their_links(self) -> None:
        # Nested list items are indented four spaces far more often than code is.
        self.write("notes/nested.md", "- Üst madde\n    - [[kavram-bir]] alt madde\n\t- [[kavram-iki]] sekmeli\n")
        links = build_links(self.source.snapshot())
        self.assertEqual(set(links.outgoing[make_rid("notes/nested.md")]), {
            make_rid("knowledge/concepts/kavram-bir.md"), make_rid("knowledge/concepts/kavram-iki.md"),
        })

    def test_index_and_rejected_records_are_neither_sources_nor_targets(self) -> None:
        self.write("notes/generated-task.md", "---\nkind: task\ngenerated: true\n---\n[[atlas]]")
        self.write("notes/exclusions.md", "[[generated-task]] [[reddedilen]] [[outcomes]] [[gizli]]")
        snapshot = self.source.snapshot()
        links = build_links(snapshot)
        excluded = {make_rid(path) for path in (
            "notes/generated-task.md", "knowledge/concepts/reddedilen.md", "knowledge/v3/outcomes.md",
        )}
        for mapping in (links.outgoing, links.incoming, links.unresolved):
            self.assertTrue(excluded.isdisjoint(mapping))
        self.assertEqual(links.unresolved[make_rid("notes/exclusions.md")], (
            "generated-task", "gizli", "outcomes", "reddedilen",
        ))

    def test_deterministic_order_and_immutable_maps(self) -> None:
        snapshot = self.source.snapshot()
        reversed_snapshot = replace(snapshot, records=dict(reversed(list(snapshot.records.items()))))
        first = build_links(snapshot)
        second = build_links(reversed_snapshot)
        self.assertEqual(first, second)
        for field in ("outgoing", "incoming", "unresolved"):
            self.assertEqual(list(getattr(first, field).items()), list(getattr(second, field).items()))
        mutable = {"source": ["target"]}
        index = LinkIndex(mutable, {}, {})
        mutable["source"].append("other")
        self.assertEqual(index.outgoing["source"], ("target",))
        with self.assertRaises(TypeError):
            index.outgoing["source"] = ()


if __name__ == "__main__":
    unittest.main()
