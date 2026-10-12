from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

from beyin_web.vault.records import make_rid
from tests.e2e.support import PageTestCase


class JournalTests(PageTestCase):
    beyin = False

    def filled(self, date: str) -> None:
        self.wait_for(f'.journal-page[data-date="{date}"][aria-busy="false"]')

    def open_day(self, date: str) -> None:
        self.open(f"#/gunlukler/{date}")
        self.filled(date)

    @staticmethod
    def receipt_selector(number: int) -> str:
        return f'.journal-receipt[data-rid="{make_rid("receipts/" + str(number).zfill(64) + ".md")}"]'

    def go_day(self, selector: str, date: str) -> None:
        self.wait_for(selector).click()
        self.wait_until(lambda driver: self.hash() == f"#/gunlukler/{date}")
        self.filled(date)

    def test_default_date_and_golden_sections(self) -> None:
        self.open("#/gunlukler")
        self.wait_until(lambda driver: self.hash() == "#/gunlukler/2026-01-12")
        self.filled("2026-01-12")
        golden = self.golden("journal_day")
        self.assertEqual(self.text("#main h1"), self.messages["page.journal.title"])
        self.assertEqual(self.text(".journal-notice"), self.messages["journal.notice"])
        self.assertEqual(self.text("#journal-selected-date"), "12 Ocak 2026 Pazartesi")
        self.assertEqual(self.text(".journal-summary"), golden["receipts"][0]["summary"])
        self.assertEqual(self.text(".journal-receipt-time"), "15:00")
        self.assertEqual(self.text(".journal-session time"), "15:30")
        for label, value in golden["cards"][0]["items"]:
            self.assertIn(label, self.text("#journal-sessions"))
            self.assertIn(value, self.text("#journal-sessions"))
        self.assertEqual([item.text for item in self.all("#journal-changed .list-row strong")],
                         [item["title"] for item in golden["changed"]])
        self.assertEqual(self.text(".journal-file-time"), self.messages["journal.fileTime"])
        self.assertEqual([item.text for item in self.all("#journal-month .list-row strong")], ["12", "7", "6", "5"])
        self.assertEqual([item.text for item in self.all(".journal-month-count")], ["1 kayıt", "2 kayıt", "1 kayıt", "2 kayıt"])
        self.assert_clean_text()

    def test_receipt_order_learned_line_and_offset_clock(self) -> None:
        self.open_day("2026-01-05")
        receipts = self.all(".journal-receipt")
        self.assertEqual([item.get_attribute("data-event-id") for item in receipts], [str(n).zfill(64) for n in (1, 2)])
        self.assertEqual([item.text for item in self.all(".journal-receipt-time")], ["11:10", "18:30"])
        self.assertEqual([item.text for item in self.all(".journal-harness")], ["claude", "codex"])
        first, second = self.receipt_selector(1), self.receipt_selector(2)
        self.assertEqual(self.all(first + " .journal-learned"), [])
        self.assertEqual(self.text(second + " .journal-learned strong"), self.messages["journal.learned"])
        self.assertIn("Küçük adımların sonuçları ayrı ayrı izlenebilir.", self.text(second + " .journal-learned"))
        self.assertTrue(self.driver.execute_script(
            "return getComputedStyle(document.querySelector(arguments[0])).backgroundColor !== "
            "getComputedStyle(document.querySelector('#journal-timeline')).backgroundColor", second + " .journal-learned"))
        self.open_day("2026-01-06")
        self.assertEqual(self.text(self.receipt_selector(3) + " .journal-receipt-time"), "01:30")

    def test_project_inference_and_harness_badges(self) -> None:
        self.open_day("2026-01-07")
        inferred = self.receipt_selector(4) + " .journal-project"
        self.assertEqual(self.text(inferred), "cinar")
        self.assertIn("journal-project-inferred", self.wait_for(inferred).get_attribute("class"))
        # An inferred project is set apart by the soft ink colour; fading it with opacity made it unreadable.
        self.assertTrue(self.driver.execute_script(
            "const style = getComputedStyle(document.querySelector(arguments[0]));"
            "return style.opacity === '1' && style.color === getComputedStyle(document.querySelector('.journal-receipt-time')).color"
            " && style.color !== getComputedStyle(document.querySelector('.journal-harness')).color", inferred))
        self.assertEqual(self.all(self.receipt_selector(5) + " .journal-project"), [])
        self.assertEqual([item.text for item in self.all(".journal-harness")], ["claude", "claude"])
        self.open_day("2026-01-05")
        self.assertEqual(self.all(".journal-project-inferred"), [])

    def test_sessions_precede_receipts_and_source_link_opens_record(self) -> None:
        self.open_day("2026-01-12")
        self.assertTrue(self.driver.execute_script(
            "return Boolean(document.querySelector('#journal-sessions').compareDocumentPosition("
            "document.querySelector('#journal-timeline')) & Node.DOCUMENT_POSITION_FOLLOWING)"))
        record = self.golden("journal_day")["receipts"][0]["refs"][0]
        link = self.wait_for(".journal-refs a")
        self.assertTrue(link.get_attribute("href").endswith("#/not/" + record["rid"]))
        link.click()
        self.wait_until(lambda driver: self.hash() == "#/not/" + record["rid"])
        self.wait_until(lambda driver: not self.all(".journal-page"))

    def test_month_navigation_day_selection_history_and_empty_day(self) -> None:
        self.open_day("2026-01-05")
        self.wait_for('[data-month-direction="1"]').click()
        self.wait_until(lambda driver: self.text(".journal-month-label") == "Şubat 2026")
        self.assertEqual(self.hash(), "#/gunlukler/2026-01-05")
        self.assertEqual(len(self.all(".journal-calendar-day")), 28)
        self.assertIn(self.messages["journal.month.empty"], self.text("#journal-month"))
        self.wait_for('[data-month-direction="-1"]').click()
        self.wait_until(lambda driver: self.text(".journal-month-label") == "Ocak 2026")
        self.go_day('.journal-calendar-day[data-date="2026-01-06"]', "2026-01-06")
        self.driver.back()
        self.wait_until(lambda driver: self.hash() == "#/gunlukler/2026-01-05")
        self.filled("2026-01-05")
        self.go_day('.journal-calendar-day[data-date="2026-01-08"]', "2026-01-08")
        self.assertIn(self.messages["journal.day.empty"], self.text("#journal-timeline"))
        self.assertEqual(self.all(".journal-receipt"), [])
        self.assertIn(self.messages["journal.changed.empty"], self.text("#journal-changed"))

    def test_receipt_day_arrows_and_endpoints(self) -> None:
        self.open_day("2026-01-05")
        self.assertFalse(self.wait_for(".journal-previous-day").is_enabled())
        self.go_day(".journal-next-day", "2026-01-06")
        self.go_day(".journal-next-day", "2026-01-07")
        self.go_day(".journal-next-day", "2026-01-12")
        self.assertFalse(self.wait_for(".journal-next-day").is_enabled())
        self.go_day(".journal-previous-day", "2026-01-07")
        self.open_day("2026-01-08")
        self.assertEqual(self.wait_for(".journal-previous-day").get_attribute("data-day"), "2026-01-07")
        self.assertEqual(self.wait_for(".journal-next-day").get_attribute("data-day"), "2026-01-12")

    def test_heatmap_cells_today_and_calendar_dots(self) -> None:
        self.open_day("2026-01-05")
        golden = self.golden("journal_heatmap")
        cells = self.all(".journal-heatmap-cell")
        self.assertEqual(len(cells), 140)
        self.assertEqual(len(self.all(".journal-heatmap-week")), 20)
        for cell in cells:
            date = cell.get_attribute("data-date")
            self.assertEqual(cell.get_attribute("title"), self.messages["journal.dayCount"].format(date=date, count=golden["days"][date]))
        self.assertEqual(self.wait_for(".journal-today").get_attribute("data-date"), golden["today"])
        self.assertNotEqual(self.driver.execute_script(
            "return getComputedStyle(document.querySelector('.journal-today .journal-day-number')).outlineStyle"), "none")
        self.assertEqual(self.wait_for(".journal-selected").get_attribute("data-date"), "2026-01-05")
        self.assertEqual(len(self.all(".journal-day-dot")), 4)
        self.go_day('.journal-heatmap-cell[data-date="2026-01-07"]', "2026-01-07")

    def test_summary_is_plain_text_and_preserves_newlines(self) -> None:
        summary = "<b>kalın</b>\nSecond line"
        metadata = {"kind": "receipt", "event_id": "a" * 64, "harness": "codex",
                    "created_at": "2026-01-05T19:45:00+03:00", "refs": []}
        (self.vault / "receipts" / "plain.md").write_text(
            "---\n" + json.dumps(metadata, ensure_ascii=False) + "\n---\n" + summary + "\n", encoding="utf-8")
        self.restart_server()
        self.open_day("2026-01-05")
        selector = f'.journal-receipt[data-rid="{make_rid("receipts/plain.md")}"] .journal-summary'
        self.assertEqual(self.wait_for(selector).get_attribute("textContent"), summary)
        self.assertEqual(self.all(selector + " b"), [])
        self.assertEqual(self.driver.execute_script(
            "return getComputedStyle(document.querySelector(arguments[0])).whiteSpace", selector), "pre-wrap")

    def test_no_receipts_falls_back_to_server_today(self) -> None:
        for receipt in (self.vault / "receipts").glob("*.md"):
            receipt.unlink()
        self.restart_server()
        self.open("#/gunlukler")
        self.wait_until(lambda driver: self.hash() == "#/gunlukler/2026-01-12")
        self.filled("2026-01-12")
        self.assertIn(self.messages["journal.heatmap.empty"], self.text("#journal-heatmap"))
        self.assertIn(self.messages["journal.day.empty"], self.text("#journal-timeline"))
        self.assertEqual(len(self.all(".journal-heatmap-cell")), 140)
        self.assertFalse(self.wait_for(".journal-previous-day").is_enabled())
        self.assertFalse(self.wait_for(".journal-next-day").is_enabled())

    def test_errors_have_retry_and_recover_by_section(self) -> None:
        for endpoint, selector, message in [
            ("journal/heatmap", "#journal-heatmap", "journal.heatmap.error"),
            ("journal/months/2026-01", "#journal-calendar", "journal.month.error"),
            ("journal/days/2026-01-12", "#journal-timeline", "journal.day.error"),
        ]:
            with self.subTest(endpoint=endpoint):
                # Same address every time: only a new origin makes the browser load the page again.
                self.restart_server()
                original = self.server.api._build

                def failing(path: str, *args: Any) -> Any:
                    if path == endpoint:
                        raise RuntimeError("synthetic_failure")
                    return original(path, *args)

                with patch.object(self.server.api, "_build", side_effect=failing):
                    self.open("#/gunlukler/2026-01-12")
                    retry = self.wait_for(selector + " [role=alert] button")
                    self.assertEqual(retry.text, self.messages["action.retry"])
                    self.assertIn(self.messages[message], self.text(selector))
                    self.wait_until(lambda driver: self.all('.journal-page[aria-busy="false"]'))
                    errors = self.console_errors()
                    self.assertTrue(errors)
                    self.assertTrue(all("500" in entry["message"] and "/api/v1/" + endpoint in entry["message"] for entry in errors), errors)
                retry.click()
                self.filled("2026-01-12")
                self.assertEqual(self.all(selector + " [role=alert]"), [])

    def test_changed_event_refreshes_and_leaving_removes_page(self) -> None:
        self.open_day("2026-01-05")
        metadata = {"kind": "receipt", "event_id": "b" * 64, "harness": "codex",
                    "created_at": "2026-01-05T20:00:00+03:00", "refs": []}
        (self.vault / "receipts" / "new.md").write_text(
            "---\n" + json.dumps(metadata) + "\n---\nSynthetic fresh receipt\n", encoding="utf-8")
        self.driver.execute_script("document.dispatchEvent(new CustomEvent('beyin:changed'))")
        self.wait_until(lambda driver: len(self.all(".journal-receipt")) == 3)
        self.filled("2026-01-05")
        self.assertEqual(self.hash(), "#/gunlukler/2026-01-05")
        self.driver.execute_script("location.hash = '/bilgi'")
        self.wait_until(lambda driver: not self.all(".journal-page"))
        self.driver.execute_script("document.dispatchEvent(new CustomEvent('beyin:changed'))")
        self.assertEqual(self.all(".journal-page"), [])

    def test_layout_text_and_csp(self) -> None:
        self.open_day("2026-01-05")
        self.assert_no_overflow()
        self.assert_clean_text()
        self.assertEqual(self.all("#main [style], #main style, #main script"), [])
        self.open_day("2026-01-12")
        self.assert_no_overflow()
        self.assert_clean_text()
