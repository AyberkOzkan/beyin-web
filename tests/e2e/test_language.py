from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.e2e.support import PageTestCase

STATIC = Path(__file__).resolve().parents[2] / "beyin_web" / "static"
PAGES = ("home", "projects", "goals", "knowledge", "journal", "graph", "search", "memory", "reports")


def messages(language: str) -> dict[str, Any]:
    return dict(json.loads((STATIC / "i18n" / f"{language}.json").read_text(encoding="utf-8")))


class LanguageTestCase(PageTestCase):
    def document_language(self) -> str:
        return str(self.driver.execute_script("return document.documentElement.lang"))

    def menu(self) -> list[str]:
        return [link.text for link in self.all(".nav-link")]

    def switch_language(self, expected: str) -> None:
        self.wait_for(".settings-button").click()
        self.wait_for(f'.settings-language[data-language="{expected}"]').click()
        self.wait_until(lambda driver: self.document_language() == expected)
        self.wait_for("#shell:not([hidden])")
        self.wait_for("#main h1")


class LanguageSwitchTests(LanguageTestCase):
    def test_switch_translates_the_page_and_survives_a_reload(self) -> None:
        turkish, english = self.messages, messages("en")
        self.open("#/gunlukler/2026-01-12")
        self.assertEqual(self.document_language(), "tr")
        self.assertEqual(self.menu(), [turkish[f"page.{page}.title"] for page in PAGES])
        self.assertEqual(self.all(".language-switch"), [])
        self.assertIn("12 Ocak 2026 Pazartesi", self.text("#main"))

        self.switch_language("en")
        self.assertEqual(self.hash(), "#/gunlukler/2026-01-12")
        self.assertEqual(self.menu(), [english[f"page.{page}.title"] for page in PAGES])
        self.assertEqual(self.text("#main h1"), "Journal")
        self.assertEqual(self.driver.title, "Journal · Beyin")
        self.assertRegex(self.text("#main"), "Monday,? 12 January 2026")
        self.assertNotIn("Ocak", self.text("#main .journal-selected-heading"))
        count = len(self.source.snapshot().records)
        self.assertEqual(self.text("#vault-records"), f"{count} records")
        self.assertEqual(self.wait_for("#global-search").get_attribute("placeholder"), english["shell.searchPlaceholder"])
        self.assertEqual(self.wait_for(".settings-button").get_attribute("aria-label"), "Settings")

        self.driver.refresh()
        self.wait_for("#main h1")
        self.assertEqual(self.document_language(), "en")
        self.assertEqual(self.text("#main h1"), "Journal")

        self.switch_language("tr")
        self.assertEqual(self.text("#main h1"), turkish["page.journal.title"])
        self.assertEqual(self.text("#vault-records"), f"{count} kayıt")
        self.assert_clean_text()

    def test_stored_choice_that_is_not_a_language_is_ignored(self) -> None:
        self.open()
        for stored in ("de", "../en", ""):
            with self.subTest(stored=stored):
                self.driver.execute_script("localStorage.setItem('beyin-web.language', arguments[0])", stored)
                self.driver.refresh()
                self.wait_for("#main h1")
                self.assertEqual(self.document_language(), "tr")
                self.assertEqual(self.menu()[0], self.messages["page.home.title"])


class EnglishDefaultTests(LanguageTestCase):
    language = "en"
    ROUTES = (("#/", "home"), ("#/projeler", "projects"), ("#/hedefler", "goals"), ("#/bilgi", "knowledge"),
              ("#/gunlukler", "journal"), ("#/grafik", "graph"), ("#/arama?q=Atlas", "search"), ("#/hafiza", "memory"),
              ("#/raporlar", "reports"), ("#/_vitrin", "showcase"), ("#/boyle-bir-sayfa-yok", "notFound"))

    def test_every_page_opens_in_english_with_no_missing_text(self) -> None:
        greetings = {self.messages[f"home.greeting.{period}"] for period in ("morning", "day", "evening")}
        for route, page in self.ROUTES:
            with self.subTest(route=route):
                self.open(route)
                self.assertEqual(self.document_language(), "en")
                if page == "home":
                    self.wait_for('.home-page[aria-busy="false"]')
                    self.assertIn(self.text("#main h1"), greetings)
                else:
                    self.assertEqual(self.text("#main h1"), self.messages[f"page.{page}.title"])
                self.assert_clean_text()
                self.assert_no_overflow()
                log = self.driver.get_log("browser")
                self.assertEqual([entry for entry in log if entry["level"] == "SEVERE"], [])
                self.assertEqual([entry["message"] for entry in log if "Missing translation" in entry["message"]], [])

    def test_viewer_choice_wins_over_the_server_default_and_the_topbar_fits(self) -> None:
        self.open()
        self.assertEqual(self.menu(), [self.messages[f"page.{page}.title"] for page in PAGES])
        self.assertEqual(self.text(".obsidian-link"), self.messages["shell.openObsidian"])
        self.driver.set_window_size(1024, 941)
        self.wait_until(lambda driver: driver.execute_script("return window.innerWidth <= 1024"))
        self.assertTrue(self.driver.execute_script("""
            const bar = document.querySelector('#topbar');
            return bar.scrollWidth <= bar.clientWidth &&
              [...bar.querySelectorAll('a, button, input')].every(node => {
                const rect = node.getBoundingClientRect(), parent = bar.getBoundingClientRect();
                return rect.left >= parent.left && rect.right <= parent.right;
              });
        """))
        self.driver.set_window_size(1672, 941)
        self.switch_language("tr")
        self.assertEqual(self.menu(), [messages("tr")[f"page.{page}.title"] for page in PAGES])
        self.driver.refresh()
        self.wait_for("#main h1")
        self.assertEqual(self.document_language(), "tr")
