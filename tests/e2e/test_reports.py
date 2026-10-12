from __future__ import annotations

from typing import Any
from unittest.mock import patch

from tests.e2e.support import PageTestCase


class ReportsTests(PageTestCase):
    beyin = False

    def filled(self, start: str = "2026-01-05") -> None:
        self.wait_for(f'.reports-page[data-week="{start}"][aria-busy="false"]')

    def open_report(self) -> None:
        self.open("#/raporlar?hafta=2026-01-07")
        self.filled()

    def test_navigation_and_five_golden_cards(self) -> None:
        self.open()
        self.wait_for('#navigation a[href="#/raporlar"]').click()
        self.filled("2026-01-12")
        self.assertEqual(self.text("#main h1"), self.messages["page.reports.title"])
        self.assertEqual(self.text(".reports-notice"), self.messages["reports.notice"])
        self.open_report()
        data = self.golden("reports")
        self.assertEqual(len(self.all(".reports-grid > .card")), 5)
        self.assertEqual(self.text("#reports-range"), "5–11 Ocak 2026")
        for period in ("week", "month"):
            for key in ("receipts", "worked_notes", "learned_count", "active_days"):
                expected = str(data[period][key])
                if key == "active_days":
                    expected += " / " + ("7" if period == "week" else "30")
                self.assertEqual(self.text(f'#reports-{period} [data-stat="{key}"] strong'), expected)
        for key, count in data["knowledge"]["counts"].items():
            self.assertEqual(self.text(f'#reports-knowledge [data-count="{key}"] strong'), str(count))
        self.assertEqual(len(self.all("#reports-week rect")), 7)
        self.assertEqual(len(self.all("#reports-month circle")), 30)
        self.assertEqual([item.text for item in self.all(".reports-project h3")],
                         [project["title"] for project in data["projects"]])
        for item, project in zip(self.all(".reports-project"), data["projects"]):
            self.assertIn(f'bu hafta {project["week_receipts"]} · 30 günde {project["month_receipts"]} işlem kaydı', item.text)
            self.assertIn(f'{project["open_tasks"]} açık görev', item.text)
        self.assertEqual([item.text for item in self.all(".reports-learned p")], [item["text"] for item in data["learned"]])
        self.assertEqual(len(self.all(".reports-worked")), len(data["knowledge"]["most_worked"]))
        self.assert_clean_text()

    def test_distribution_bars_are_proportional_and_named_by_project_title(self) -> None:
        self.open_report()
        data = self.golden("reports")
        groups = data["knowledge"]["by_project"]
        titles = {project["name"]: project["title"] for project in data["projects"]}
        largest = max(group["notes"] + group["knowledge"] for group in groups)
        rows = self.all(".reports-distribution")
        self.assertEqual([row.find_element("css selector", "span").text for row in rows],
                         [self.messages["reports.general"] if group["project"] is None
                          else titles.get(group["project"], group["project"]) for group in groups])
        for row, group in zip(rows, groups):
            # The bar once kept the aspect ratio of its viewBox and filled a quarter of the track at most.
            track, bar = self.driver.execute_script(
                "const svg = arguments[0].querySelector('svg');"
                "return [svg.getBoundingClientRect().width, svg.querySelector('rect').getBoundingClientRect().width]", row)
            self.assertGreater(track, 100)
            self.assertAlmostEqual(bar / track, (group["notes"] + group["knowledge"]) / largest, delta=0.02)

    def test_week_selection_history_and_current_week_controls(self) -> None:
        self.open_report()
        self.wait_for("#reports-previous").click()
        self.wait_until(lambda driver: self.hash() == "#/raporlar?hafta=2025-12-29")
        self.filled("2025-12-29")
        self.assertEqual(self.text('#reports-week [data-stat="receipts"] strong'), "0")
        self.driver.back()
        self.wait_until(lambda driver: self.hash() == "#/raporlar?hafta=2026-01-07")
        self.filled()
        self.assertEqual(self.text('#reports-week [data-stat="receipts"] strong'), str(self.golden("reports")["week"]["receipts"]))
        self.wait_for("#reports-next").click()
        self.filled("2026-01-12")
        self.assertEqual(self.hash(), "#/raporlar?hafta=2026-01-12")
        self.assertFalse(self.wait_for("#reports-next").is_enabled())
        self.assertFalse(self.wait_for("#reports-current").is_enabled())
        self.wait_for("#reports-previous").click()
        self.filled()
        self.wait_for("#reports-current").click()
        self.wait_until(lambda driver: self.hash() == "#/raporlar")
        self.filled("2026-01-12")

    def test_project_learned_and_record_links(self) -> None:
        golden = self.golden("reports")
        cases = [
            (".reports-project a", "#/projeler/" + golden["projects"][0]["name"]),
            (".reports-learned", "#/gunlukler/" + golden["learned"][0]["day"]),
            (".reports-worked", "#/not/" + golden["knowledge"]["most_worked"][0]["record"]["rid"]),
        ]
        for selector, address in cases:
            with self.subTest(selector=selector):
                self.open_report()
                self.wait_for(selector).click()
                self.wait_until(lambda driver: self.hash() == address)
                self.wait_until(lambda driver: not self.all(".reports-page"))

    def test_no_receipts_shows_empty_graphs_and_learned(self) -> None:
        for receipt in (self.vault / "receipts").glob("*.md"):
            receipt.unlink()
        self.restart_server()
        self.open_report()
        for key in ("week", "month", "learned"):
            self.assertIn(self.messages[f"reports.{key}.empty"], self.text("#reports-" + key))
        self.assertEqual(self.all(".reports-chart"), [])
        self.assert_clean_text()

    def test_errors_in_all_cards_retry_the_request(self) -> None:
        original = self.server.api._build

        def failing(path: str, *args: Any) -> Any:
            if path == "reports":
                raise RuntimeError("synthetic_failure")
            return original(path, *args)

        with patch.object(self.server.api, "_build", side_effect=failing):
            self.open("#/raporlar?hafta=2026-01-07")
            retry = self.wait_for("#reports-week [role=alert] button")
            self.wait_for('.reports-page[aria-busy="false"]')
            self.assertEqual(len(self.all(".reports-grid [role=alert]")), 5)
            self.assertEqual(retry.text, self.messages["action.retry"])
            errors = self.console_errors()
            self.assertTrue(errors)
            self.assertTrue(all("500" in entry["message"] and "/api/v1/reports" in entry["message"] for entry in errors), errors)
        retry.click()
        self.filled()
        self.assertEqual(self.all(".reports-grid [role=alert]"), [])

    def test_layout_accessible_charts_text_and_csp(self) -> None:
        self.open_report()
        self.assert_no_overflow((1024, 1200, 1672))
        self.assert_clean_text()
        self.assertEqual(self.all("#main [style], #main style, #main script"), [])
        for chart in self.all(".reports-chart"):
            self.assertEqual(chart.get_attribute("role"), "img")
            self.assertTrue(chart.get_attribute("aria-label"))
        self.assertTrue(all(item.get_attribute("textContent") for item in self.all("#reports-week rect title")))
