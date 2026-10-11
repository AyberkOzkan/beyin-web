from __future__ import annotations

import random
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from beyin_web.vault.companion import (
    Rule, Thread, load_companion, parse_last_session, parse_rules, parse_threads,
)
from beyin_web.vault.scan import MarkdownSource, VaultSnapshot
from tests.support import make_vault


class CompanionFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = make_vault(Path(temporary.name))
        self.snapshot = MarkdownSource(self.vault).snapshot()
        self.memory = {record.role: record for record in self.snapshot.records.values() if record.role}

    def with_bodies(self, body: str) -> VaultSnapshot:
        return replace(self.snapshot, records={rid: replace(record, body=body)
                       if record.role in ("threads", "last_session", "rules") else record
                       for rid, record in self.snapshot.records.items()})

    def test_fixture_threads(self) -> None:
        document = parse_threads(self.memory["threads"].body)
        self.assertTrue(document.structured)
        self.assertEqual(document.raw, self.memory["threads"].body)
        self.assertEqual(len(document.active), 2)
        self.assertEqual(len(document.closed), 1)
        first, free = document.active
        self.assertEqual(replace(first, raw=""), Thread(
            title="Atlas değerlendirmesi", owner="Deniz", status="Etkin", status_date="2026-01-07",
            open="İkinci örnek tamamlanacak.", next_step="Atlas A3 görevini gözden geçir.",
        ))
        self.assertEqual(replace(free, raw=""), Thread(title="Çınar için serbest konu"))
        self.assertIn("Bu konu etiket kullanmadan yazılmış serbest metindir.", free.raw)
        closed = document.closed[0]
        self.assertEqual(replace(closed, raw=""), Thread(
            title="İlk hazırlık", owner="Deniz", status="Kapandı", status_date="2026-01-05",
            open="Yok.", next_step="Yok.",
        ))

    def test_fixture_cards(self) -> None:
        cards = parse_last_session(self.memory["last_session"].body)
        self.assertIsInstance(cards, list)
        self.assertTrue(cards.structured)
        self.assertEqual(cards.raw, self.memory["last_session"].body)
        self.assertEqual(len(cards), 2)
        first, second = cards
        self.assertEqual((first.date, first.time, first.label, first.session),
                         ("2026-01-12", "15:30", "claude", "session-cinar-20260112"))
        self.assertEqual(first.items, (("Özet", "Çınar projesinin değerlendirmesi hazırlandı."),
                                      ("Sonraki adım", "İlk görevi gözden geçir.")))
        self.assertEqual(first.next_step, "İlk görevi gözden geçir.")
        self.assertEqual((second.date, second.time, second.label, second.session),
                         ("2026-01-05", "", "codex", "win-offline"))
        self.assertEqual(second.items, (("Özet", "Atlas örneği çevrimdışı incelendi."),
                                       ("Sonraki adım", "Kavram bir notunu oku.")))
        self.assertEqual(second.next_step, "Kavram bir notunu oku.")
        self.assertNotIn("Önceki oturumlar", second.raw)

    def test_fixture_rules(self) -> None:
        document = parse_rules(self.memory["rules"].body)
        self.assertTrue(document.structured)
        self.assertEqual(document.raw, self.memory["rules"].body)
        self.assertEqual(len(document.rules), 3)
        first, second, free = document.rules
        self.assertEqual(replace(first, raw=""), Rule(
            date="2026-01-05", title="Küçük adımlar", scope="atlas", text="Her adımı ayrı değerlendir.",
            reason="Sonuçların kaynağı açık kalır.", source="notes/atlas.md",
        ))
        self.assertEqual(replace(second, raw=""), Rule(
            date="2026-01-07", title="Kısa açıklama", scope="genel", text="Açıklamayı kısa tut.",
            source="notes/serbest.md",
        ))
        self.assertEqual(replace(free, raw=""), Rule(
            text="Serbest biçimli bu madde yapılandırılmış kural değildir.",
        ))
        self.assertEqual(free.raw, "- Serbest biçimli bu madde yapılandırılmış kural değildir.\n")

    def test_load_uses_roles_and_keeps_identity_untouched(self) -> None:
        records = {rid: replace(record, path=f"renamed/{record.role}.md")
                   for rid, record in self.snapshot.records.items() if record.role}
        records["soul-id"] = replace(self.memory["core"], rid="soul-id", role="soul", path="renamed/identity.md")
        snapshot = replace(self.snapshot, companion_dir=None, records=records)
        with patch.object(Path, "read_text", side_effect=AssertionError("Unexpected filesystem read")):
            companion = load_companion(snapshot)
        self.assertEqual(len(companion.threads.active), 2)
        self.assertEqual(len(companion.cards), 2)
        self.assertEqual(len(companion.rules.rules), 3)
        self.assertEqual(companion.core_rid, self.memory["core"].rid)
        self.assertEqual(companion.soul_rid, "soul-id")
        self.assertEqual(companion.journal_rid, self.memory["journal"].rid)
        self.assertEqual(companion.warnings, ())
        self.assertEqual(snapshot.records[self.memory["core"].rid].body, self.memory["core"].body)

    def test_unstructured_warnings_once_per_file_without_mutating_snapshot(self) -> None:
        text = "\ufeffSerbest **Markdown**.\r\nİkinci satır.\r\n"
        snapshot = replace(self.with_bodies(text), warnings=("walk_error",))
        companion = load_companion(snapshot)
        self.assertEqual(companion.warnings, tuple(f"{role}_unstructured: {self.memory[role].path}"
                                                  for role in ("threads", "last_session", "rules")))
        self.assertEqual(snapshot.warnings, ("walk_error",))
        for document in (companion.threads, companion.cards, companion.rules):
            self.assertFalse(document.structured)
            self.assertEqual(document.raw, text)

    def test_empty_bodies_and_missing_files(self) -> None:
        companion = load_companion(self.with_bodies(""))
        self.assertEqual(len(companion.warnings), 3)
        self.assertEqual(companion.threads.active, ())
        self.assertEqual(companion.cards, [])
        self.assertEqual(companion.rules.rules, ())
        for missing in ("threads", "last_session", "rules", "core", "soul", "journal"):
            with self.subTest(missing=missing):
                snapshot = replace(self.snapshot, records={rid: record
                                   for rid, record in self.snapshot.records.items() if record.role != missing})
                companion = load_companion(snapshot)
                self.assertEqual(companion.warnings, ())
                if missing == "threads":
                    self.assertEqual(companion.threads.active, ())
                elif missing == "last_session":
                    self.assertEqual(companion.cards, [])
                elif missing == "rules":
                    self.assertEqual(companion.rules.rules, ())
                else:
                    self.assertIsNone(getattr(companion, f"{missing}_rid"))
        for role in ("threads", "last_session", "rules"):
            (self.vault / self.memory[role].path).write_text("", encoding="utf-8")
        snapshot = MarkdownSource(self.vault, companion_dir=self.snapshot.companion_dir).snapshot()
        companion = load_companion(snapshot)
        self.assertEqual(companion.threads.active, ())
        self.assertEqual(companion.cards, [])
        self.assertEqual(companion.rules.rules, ())
        self.assertEqual(companion.warnings, ())

    def test_missing_memory_directory(self) -> None:
        snapshot = replace(self.snapshot, companion_dir=None, records={rid: record
                           for rid, record in self.snapshot.records.items() if record.role is None})
        self.assertIsNone(snapshot.companion_dir)
        companion = load_companion(snapshot)
        self.assertEqual(companion.threads.active, ())
        self.assertEqual(companion.threads.closed, ())
        self.assertEqual(companion.cards, [])
        self.assertEqual(companion.rules.rules, ())
        self.assertIsNone(companion.core_rid)
        self.assertIsNone(companion.soul_rid)
        self.assertIsNone(companion.journal_rid)
        self.assertEqual(companion.warnings, ())

    def test_fixture_parsing_with_bom_and_crlf(self) -> None:
        for role, parser in (("threads", parse_threads), ("last_session", parse_last_session),
                             ("rules", parse_rules)):
            with self.subTest(role=role):
                body = self.memory[role].body
                text = "\ufeff" + body.replace("\n", "\r\n")
                document = parser(text)
                self.assertTrue(document.structured)
                self.assertEqual(document.raw, text)
                if role == "threads":
                    self.assertEqual(document.active[0].status_date, "2026-01-07")
                    blocks = document.active + document.closed
                elif role == "last_session":
                    self.assertEqual(document[0].time, "15:30")
                    blocks = document
                else:
                    self.assertEqual(document.rules[0].scope, "atlas")
                    blocks = document.rules
                for block in blocks:
                    self.assertIn("\r\n", block.raw)
                    self.assertIn(block.raw, text)


class CompanionParserTests(unittest.TestCase):
    def test_thread_section_aliases(self) -> None:
        for active in ("Active Threads", "Aktif Konular", "Açık Konular"):
            for closed in ("Closed Threads", "Kapanan", "Kapalı Konular"):
                with self.subTest(active=active, closed=closed):
                    text = f"## {active.upper()}\n### Etkin\nMetin.\n## {closed.upper()}\n### Kapalı\nSon.\n"
                    document = parse_threads(text)
                    self.assertEqual([thread.title for thread in document.active], ["Etkin"])
                    self.assertEqual([thread.title for thread in document.closed], ["Kapalı"])

    def test_threads_without_sections_and_unknown_sections(self) -> None:
        text = "Giriş.\n### Bir\nİlk metin.\n### İki\nİkinci metin.\n"
        document = parse_threads(text)
        self.assertTrue(document.structured)
        self.assertEqual([thread.title for thread in document.active], ["Bir", "İki"])
        self.assertEqual(document.active[0].raw, "### Bir\nİlk metin.\n")
        self.assertEqual(document.active[1].raw, "### İki\nİkinci metin.\n")
        text = "## Başka bölüm\n### Bir\nMetin.\n## Active Threads\n### İki\nMetin.\n"
        document = parse_threads(text)
        self.assertEqual([thread.title for thread in document.active], ["İki"])
        self.assertEqual(document.raw, text)
        document = parse_threads("### C#\nMetin.\n### İkinci konu ###\nMetin.\n")
        self.assertEqual([thread.title for thread in document.active], ["C#", "İkinci konu"])

    def test_thread_labels_and_previous_status_order(self) -> None:
        text = ("### Konu\n- **Owner:** Deniz\n- **Status (2026-01-01):** İlk\n"
                "- **Bilgi:** Ek bilgi\n- **Son durum (not 2026-01-02 ve 2026-01-03):** Son\n"
                "- **Open:** Soru\n- **Next step:** Devam\nEtiketsiz ayrıntı.\n")
        thread = parse_threads(text).active[0]
        self.assertEqual((thread.owner, thread.status, thread.status_date, thread.open, thread.next_step),
                         ("Deniz", "Son", "2026-01-02", "Soru", "Devam"))
        self.assertEqual(thread.extra, (("Status (2026-01-01)", "İlk"), ("Bilgi", "Ek bilgi")))
        self.assertEqual(thread.raw, text)
        thread = parse_threads(text + "- **Durum:** Tarihsiz\n").active[0]
        self.assertEqual((thread.status, thread.status_date), ("Tarihsiz", ""))
        self.assertEqual(thread.extra[-1], ("Son durum (not 2026-01-02 ve 2026-01-03)", "Son"))

    def test_cards_preserve_label_separators_and_optional_session(self) -> None:
        text = ("## 2026-01-01 09:05 · Atlas · Çınar · win-offline\n- **Not:** Bir\n"
                "## 2026-01-02 · Atlas · Çınar\n- **Not:** İki\n"
                "## 2026-01-03 · codex\nMetin.\n"
                "## 2026-01-04 · Atlas · short\n"
                "## 2026-01-05 · Atlas · ABCDEF\n")
        cards = parse_last_session(text)
        self.assertEqual([(card.date, card.time, card.label, card.session) for card in cards], [
            ("2026-01-01", "09:05", "Atlas · Çınar", "win-offline"),
            ("2026-01-02", "", "Atlas · Çınar", ""),
            ("2026-01-03", "", "codex", ""),
            ("2026-01-04", "", "Atlas · short", ""),
            ("2026-01-05", "", "Atlas · ABCDEF", ""),
        ])
        self.assertEqual(cards[0].items, (("Not", "Bir"),))
        self.assertEqual(cards[2].items, ())
        self.assertIn("Metin.", cards[2].raw)

    def test_previous_sections_stop_all_following_cards(self) -> None:
        for heading in ("Önceki oturumlar", "Previous", "ÖNCEKİ OTURUMLAR", "PREVIOUS"):
            with self.subTest(heading=heading):
                text = ("## 2026-01-01 · İlk\n- **Sonraki adım:** Devam\n"
                        f"## {heading}\n## 2025-12-31 · Eski · win-offline\n"
                        "## 2026-01-02 · Daha yeni\n")
                cards = parse_last_session(text)
                self.assertEqual(len(cards), 1)
                self.assertEqual(cards[0].next_step, "Devam")
                self.assertEqual(cards.raw, text)
                self.assertNotIn(heading, cards[0].raw)

    def test_rule_optional_fields_and_reason_aliases(self) -> None:
        for reason in ("neden", "gerekçe", "why"):
            for source in ("Kaynak", "Source"):
                with self.subTest(reason=reason, source=source):
                    text = f"- **2026-01-01 · Başlık (kapsam: genel):** Kural. **{reason}:** Sebep. {source}: not.md\n"
                    rule = parse_rules(text).rules[0]
                    self.assertEqual(rule, Rule("2026-01-01", "Başlık", "genel", "Kural.", "Sebep.", "not.md", text))
        text = "- **2026-01-01 · Başlık:** Kural.\n"
        self.assertEqual(parse_rules(text).rules[0], Rule("2026-01-01", "Başlık", "", "Kural.", "", "", text))
        text = "- **2026-01-01 · Başlık:** Kural. **why:** Sebep.\n"
        self.assertEqual(parse_rules(text).rules[0].reason, "Sebep.")
        self.assertEqual(parse_rules(text).rules[0].source, "")

    def test_multiline_and_malformed_rules_are_preserved(self) -> None:
        first = "- **2026-01-01 · Başlık:** Kural.\n  Devamı. **gerekçe:** İlk sebep.\n  İkinci sebep. Source: not.md\n"
        second = "- **Biçimsiz:** Kural metni.\n  Açıklama.\n"
        document = parse_rules(first + second)
        self.assertTrue(document.structured)
        self.assertEqual(document.rules[0].text, "Kural.\n  Devamı.")
        self.assertEqual(document.rules[0].reason, "İlk sebep.\n  İkinci sebep.")
        self.assertEqual(document.rules[0].source, "not.md")
        self.assertEqual(document.rules[0].raw, first)
        self.assertEqual(document.rules[1], Rule(text="**Biçimsiz:** Kural metni.\n  Açıklama.", raw=second))
        malformed = parse_rules(second)
        self.assertFalse(malformed.structured)
        self.assertEqual(malformed.raw, second)

    def test_bom_on_first_structure_and_fenced_examples(self) -> None:
        self.assertEqual(parse_threads("\ufeff### Başlık\r\nMetin.").active[0].title, "Başlık")
        self.assertEqual(parse_last_session("\ufeff## 2026-01-01 · Etiket")[0].label, "Etiket")
        text = "\ufeff- **2026-01-01 · Başlık:** Kural.\r\n"
        self.assertEqual(parse_rules(text).rules[0], Rule("2026-01-01", "Başlık", "", "Kural.", "", "", text))
        text = ("```md\n### Sahte konu\n## 2026-01-01 · Sahte kart\n"
                "- **2026-01-01 · Sahte kural:** Metin.\n```\n")
        for parser in (parse_threads, parse_last_session, parse_rules):
            document = parser(text)
            self.assertFalse(document.structured)
            self.assertEqual(document.raw, text)

    def test_free_empty_and_malformed_inputs_never_raise(self) -> None:
        inputs = ["", "\ufeff", "\r\n", "Serbest metin.\r\n", "##", "###", "- **", "- -", "- ",
                  "## 2026-01-01 · \n", "## invalid · label", "- **2026-01-01 · :** Metin."]
        generator = random.Random(3)
        alphabet = "#-*(): ·\n\r\t\ufeff0123456789abcİıÇğş\x00"
        inputs.extend("".join(generator.choices(alphabet, k=generator.randrange(300))) for _ in range(100))
        for text in inputs:
            for parser in (parse_threads, parse_last_session, parse_rules):
                with self.subTest(parser=parser.__name__, text=text):
                    first = parser(text)
                    second = parser(text)
                    self.assertEqual(first, second)
                    self.assertEqual(first.raw, text)
        for parser in (parse_threads, parse_last_session, parse_rules):
            for text in ("", "Serbest metin.\r\n"):
                self.assertFalse(parser(text).structured)


if __name__ == "__main__":
    unittest.main()
