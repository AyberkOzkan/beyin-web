from __future__ import annotations

from typing import Any
from unittest.mock import patch

from beyin_web.runtime.beyin_cli import RuntimeUnavailable
from tests.e2e.support import PageTestCase


class SearchTests(PageTestCase):
    def filled(self) -> None:
        self.wait_for('.search-results[aria-busy="false"] .search-result')
        self.wait_for(".search-summary")

    def type_query(self, value: str, enter: bool = False) -> None:
        from selenium.webdriver.common.keys import Keys
        query = self.wait_for("#search-query")
        query.send_keys(Keys.CONTROL, "a")
        query.send_keys(value)
        if enter:
            query.send_keys(Keys.ENTER)

    def rids(self) -> list[str]:
        return [card.get_attribute("data-rid") for card in self.all(".search-result")]

    def test_golden_results_highlights_and_card_navigation(self) -> None:
        expected = self.golden("search")["results"]
        self.open("#/arama?q=Atlas")
        self.filled()
        self.assertEqual(self.text("#main h1"), self.messages["page.search.title"])
        self.assertEqual(self.rids(), [record["rid"] for record in expected])
        self.assertEqual([heading.text for heading in self.all(".search-result h2")], [record["title"] for record in expected])
        self.assertEqual(self.text(".search-result mark"), "Atlas")
        self.assertEqual(self.all(".search-snippet")[0].get_attribute("textContent"), expected[0]["snippet"])
        self.assertEqual(self.all(".search-path")[0].text, expected[0]["path"])
        self.assertEqual(self.all(".search-project-badge")[0].text, expected[0]["project"])
        self.assertTrue(self.all(".search-result time"))
        self.assertIn(str(len(expected)), self.text(".search-summary"))
        self.assert_clean_text()
        self.assert_no_overflow()
        self.wait_for(".search-result").click()
        self.wait_until(lambda driver: self.hash() == "#/not/" + expected[0]["rid"])

    def test_ascii_query_highlights_original_turkish_word(self) -> None:
        note = self.vault / "notes" / "work.md"
        note.write_text("---\nkind: note\ntitle: Synthetic work\n---\nBu çalışma tamamlandı.\n", encoding="utf-8")
        self.restart_server()
        self.open("#/arama?q=calisma")
        self.filled()
        self.assertEqual([mark.text for mark in self.all(".search-result mark")], ["çalışma"])

    def test_typing_replaces_history_enter_commits_and_back_restores(self) -> None:
        self.open("#/arama")
        self.wait_for(".search-results .state")
        self.assertEqual(self.driver.execute_script("return document.activeElement.id"), "search-query")
        length = self.driver.execute_script("return history.length")
        self.driver.execute_script("""
            document.querySelector('#search-query').addEventListener('input', () => { window.lastSearchInput = performance.now(); });
            const original = window.fetch;
            window.fetch = (...args) => {
              if (String(args[0]).includes('/api/v1/search')) window.searchDelay = performance.now() - window.lastSearchInput;
              return original(...args);
            };
        """)
        self.type_query("Atlas")
        self.wait_until(lambda driver: self.hash() == "#/arama?q=Atlas")
        self.filled()
        self.assertEqual(self.driver.execute_script("return history.length"), length)
        self.assertGreaterEqual(self.driver.execute_script("return window.searchDelay"), 240)
        self.assertEqual(self.driver.execute_script("return document.activeElement.id"), "search-query")
        from selenium.webdriver.common.keys import Keys
        self.wait_for("#search-query").send_keys(Keys.ENTER)
        self.wait_until(lambda driver: driver.execute_script("return history.length") == length + 1)
        self.type_query("calisma", enter=True)
        self.wait_until(lambda driver: self.hash() == "#/arama?q=calisma")
        self.driver.back()
        self.wait_until(lambda driver: self.hash() == "#/arama?q=Atlas" and
                        driver.find_element("id", "search-query").get_attribute("value") == "Atlas")
        self.filled()
        self.assertEqual(self.rids(), [record["rid"] for record in self.golden("search")["results"]])

    def test_filters_narrow_results_and_survive_refresh(self) -> None:
        from selenium.webdriver.support.ui import Select
        self.open("#/arama?q=Atlas")
        self.filled()
        Select(self.wait_for("#search-kind")).select_by_value("note")
        self.wait_until(lambda driver: "tur=note" in self.hash())
        expected = [record for record in self.golden("search")["results"] if record["kind"] == "note"]
        self.wait_until(lambda driver: self.rids() == [record["rid"] for record in expected])
        Select(self.wait_for("#search-project")).select_by_value("atlas")
        expected = [record for record in expected if record["project"] == "atlas"]
        self.wait_until(lambda driver: "proje=atlas" in self.hash() and self.rids() == [record["rid"] for record in expected])
        address = self.hash()
        self.driver.refresh()
        self.filled()
        self.assertEqual(self.hash(), address)
        self.assertEqual(self.wait_for("#search-query").get_attribute("value"), "Atlas")
        self.assertEqual(Select(self.wait_for("#search-kind")).first_selected_option.get_attribute("value"), "note")
        self.assertEqual(Select(self.wait_for("#search-project")).first_selected_option.get_attribute("value"), "atlas")
        self.assertEqual(self.rids(), [record["rid"] for record in expected])

    def test_beyin_mode_and_selector(self) -> None:
        self.open("#/arama?q=Atlas&kip=beyin")
        self.filled()
        expected = self.golden("search_beyin")["results"]
        self.assertEqual(self.text(".search-explanation"), self.messages["search.beyinDescription"])
        self.assertEqual(self.rids(), [record["rid"] for record in expected])
        self.assertEqual(self.text(".search-snippet"), expected[0]["text"])
        self.assertEqual(len(self.all(".search-modes [role=tab]")), 2)
        self.wait_for('.search-modes [role=tab][aria-selected="false"]').click()
        self.wait_until(lambda driver: "kip=" not in self.hash() and len(self.rids()) == len(self.golden("search")["results"]))
        self.assertEqual(self.all(".search-explanation"), [])

    def test_empty_query_no_results_private_records_and_clear(self) -> None:
        self.open("#/arama")
        self.assertEqual(self.text(".search-results .state-title"), self.messages["search.hintTitle"])
        for query in ("zzzz-no-match", "GIZLI-SIZINTI-ISARETI"):
            self.type_query(query, enter=True)
            self.wait_until(lambda driver: self.text(".search-results .state-title") == self.messages["search.noResultsTitle"])
            self.assertEqual(self.rids(), [])
            self.assertIn(self.messages["search.noResults"], self.text(".search-results"))
        self.wait_for(".search-form .icon-button").click()
        self.wait_until(lambda driver: self.hash() == "#/arama")
        self.assertEqual(self.text(".search-results .state-title"), self.messages["search.hintTitle"])

    def test_beyin_long_plain_text_warnings_and_omitted(self) -> None:
        text = "<script>synthetic</script>\n" + "Long plain text\n" * 60
        response: dict[str, Any] = {"records": [{"source": "notes/Çınar Projesi.md", "text": text}],
                                    "stale_count": 2, "omitted_count": 3, "abstained": False}
        with patch.object(self.runtime, "context", return_value=response):
            self.open("#/arama?q=Atlas&kip=beyin")
            self.filled()
            self.assertIn(self.messages["search.stale"], self.text(".search-notices"))
            self.assertIn(self.messages["search.omitted"].replace("{count}", "3"), self.text(".search-notices"))
            self.assertEqual(self.wait_for(".search-snippet").get_attribute("textContent"), text)
            self.assertEqual(self.all(".search-snippet script"), [])
            more = self.wait_for(".search-more")
            self.assertEqual(more.get_attribute("aria-expanded"), "false")
            more.click()
            self.assertEqual(more.get_attribute("aria-expanded"), "true")
            self.assertEqual(self.all(".search-collapsed"), [])
            self.assert_no_overflow()
            self.assert_clean_text()

    def test_runtime_errors_and_retry(self) -> None:
        for code, status in (("runtime_unavailable", "503"), ("timeout", "504")):
            with self.subTest(code=code):
                # Same address as the previous case: without a new origin the browser would
                # keep the already loaded page instead of requesting again.
                self.restart_server()
                with patch.object(self.runtime, "context", side_effect=RuntimeUnavailable(code)):
                    self.open("#/arama?q=Atlas&kip=beyin")
                    retry = self.wait_for(".search-results [role=alert] button")
                    self.assertIn(self.messages["search.beyinUnavailable"], self.text(".search-results"))
                    errors = self.console_errors()
                    self.assertTrue(errors)
                    self.assertTrue(all(status in entry["message"] and "/api/v1/search" in entry["message"] for entry in errors), errors)
                retry.click()
                self.filled()
                self.assertEqual(self.all(".search-results [role=alert]"), [])


class PlainSearchTests(PageTestCase):
    beyin = False

    def test_unavailable_mode_falls_back_and_does_not_render_selector(self) -> None:
        self.open("#/arama?q=Atlas&kip=beyin")
        self.wait_for('.search-results[aria-busy="false"] .search-result')
        self.wait_until(lambda driver: self.hash() == "#/arama?q=Atlas")
        self.assertEqual(self.all(".search-modes [role=tab]"), [])
        self.assertEqual(self.all(".search-explanation"), [])
        self.assertEqual([card.get_attribute("data-rid") for card in self.all(".search-result")],
                         [record["rid"] for record in self.golden("search")["results"]])
        self.assert_clean_text()
        self.assert_no_overflow()
