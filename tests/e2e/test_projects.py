from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

from tests.e2e.support import PageTestCase


class ProjectsTests(PageTestCase):
    beyin = False
    display_name = "Deniz"

    def filled(self, name: str) -> None:
        self.wait_until(lambda driver: self.hash().split("?")[0] == f"#/projeler/{name}")
        self.wait_for('.projects-page[aria-busy="false"] #projects-detail-title')
        self.wait_for("#projects-note.markdown-body, #projects-note .markdown-body, #projects-note .state")

    def test_default_selects_newest_and_replaces_history_entry(self) -> None:
        projects = self.golden("projects")["projects"]
        newest = max(projects, key=lambda project: datetime.fromisoformat(project["last_activity"]))
        self.open("#/")
        self.wait_for('.home-page[aria-busy="false"]')
        self.wait_for('.nav-link[data-page="projects"]').click()
        self.filled(newest["name"])
        self.assertEqual(self.hash(), f'#/projeler/{newest["name"]}')
        self.assertEqual(len(self.all(".projects-project")), 2)
        self.assertEqual({item.get_attribute("data-project") for item in self.all(".projects-project")},
                         {project["name"] for project in projects})
        self.driver.back()
        self.wait_for('.home-page[aria-busy="false"]')
        self.assertEqual(self.hash(), "#/")
        self.assert_clean_text()

    def test_atlas_roadmap_note_wikilinks_and_knowledge(self) -> None:
        self.open("#/projeler/atlas")
        self.filled("atlas")
        data = self.golden("project")
        rows = self.all("#projects-tasks .projects-task")
        self.assertEqual(len(rows), 6)
        icons = {"done": "circle-check", "active": "circle-dot", "waiting": "circle-pause", "blocked": "circle-x",
                 "inbox": "circle", "cancelled": "ban"}
        for row, task in zip(rows, data["tasks"], strict=True):
            self.assertEqual(row.get_attribute("data-status"), task["status"])
            self.assertEqual(row.find_element("css selector", "strong").text, task["title"])
            self.assertEqual(row.find_element("css selector", "use").get_attribute("href"), f'#{icons[task["status"]]}')
            self.assertTrue(row.get_attribute("href").endswith(f'#/not/{task["rid"]}'))
            if task["next_action"]:
                self.assertIn(task["next_action"], row.text)
        self.assertEqual(self.all('#projects-tasks input[type="checkbox"]'), [])
        for css in ('.projects-status', '.projects-project[data-project="atlas"]'):
            meter = self.wait_for(css + " meter")
            self.assertEqual(meter.get_attribute("value"), "2")
            self.assertEqual(meter.get_attribute("max"), "5")
            self.assertIn("2 / 5", self.text(css))
        cancelled = self.wait_for('.projects-task[data-status="cancelled"] strong')
        self.assertIn("line-through", self.driver.execute_script("return getComputedStyle(arguments[0]).textDecorationLine", cancelled))
        # The note's own "# Atlas" heading repeats the project title printed above it and is dropped.
        self.assertEqual(self.all("#projects-note h1"), [])
        self.assertIn("sentetik projedir", self.text("#projects-note"))
        self.assertIn("[[kod-icinde]]", self.text("#projects-note pre"))
        record = data["knowledge"][0]
        self.assertIn(record["title"], self.text("#projects-knowledge"))
        self.assertTrue(self.wait_for("#projects-knowledge a").get_attribute("href").endswith(f'#/not/{record["rid"]}'))
        self.assert_clean_text()
        self.wait_for(f'#projects-note a.wikilink[href="#/not/{record["rid"]}"]').click()
        self.wait_until(lambda driver: self.hash() == f'#/not/{record["rid"]}')

    def test_cinar_navigation_back_and_direct_address(self) -> None:
        self.open("#/projeler/atlas")
        self.filled("atlas")
        self.wait_for('.projects-project[data-project="cinar"]').click()
        self.filled("cinar")
        self.assertEqual(len(self.all("#projects-tasks .projects-task")), 1)
        self.assertEqual(self.wait_for("#projects-tasks .projects-task").find_element("css selector", "use").get_attribute("href"), "#circle")
        self.assertEqual(self.text("#projects-detail-title"), self.golden("projects")["projects"][1]["title"])
        self.driver.back()
        self.filled("atlas")
        self.assertEqual(len(self.all("#projects-tasks .projects-task")), 6)
        self.open("#/projeler/cinar")
        self.filled("cinar")
        self.assertIn(self.messages["projects.knowledge.empty"], self.text("#projects-knowledge"))
        self.assert_clean_text()

    def test_receipt_and_task_routes(self) -> None:
        self.open("#/projeler/atlas")
        self.filled("atlas")
        data = self.golden("project")
        rows = self.all("#projects-receipts .list-row")
        self.assertEqual(len(rows), len(data["receipts"]))
        for row, receipt in zip(rows, data["receipts"], strict=True):
            self.assertIn(receipt["summary"], row.text)
            self.assertTrue(row.get_attribute("href").endswith(f'#/gunlukler/{receipt["time"][:10]}'))
        rows[0].click()
        self.wait_until(lambda driver: self.hash() == f'#/gunlukler/{data["receipts"][0]["time"][:10]}')
        self.open("#/projeler/atlas")
        self.filled("atlas")
        self.wait_for("#projects-tasks a").click()
        self.wait_until(lambda driver: self.hash() == f'#/not/{data["tasks"][0]["rid"]}')

    def add_quiet_project(self) -> None:
        note = self.vault / "notes" / "quiet.md"
        note.write_text('---\nkind: note\nproject: quiet\n---\n# Quiet\n\nOld project.\n', encoding="utf-8")
        timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
        os.utime(note, (timestamp, timestamp))
        self.restart_server()

    def test_filter_tabs_counts_url_and_empty_results(self) -> None:
        self.add_quiet_project()
        self.open("#/projeler/atlas")
        self.filled("atlas")
        tabs = self.all('.projects-controls [role="tab"]')
        self.assertEqual([tab.text for tab in tabs], [self.messages["projects.tab.all"].replace("{count}", "3"),
                                                     self.messages["projects.tab.active"].replace("{count}", "2")])
        quiet = self.wait_for('.projects-project[data-project="quiet"]')
        self.assertIn("projects-quiet", quiet.get_attribute("class"))
        self.assertIn(self.messages["projects.noTasks"], quiet.text)
        self.assertEqual(quiet.find_elements("css selector", "meter"), [])
        tabs[1].click()
        self.assertEqual(len(self.all(".projects-project")), 2)
        self.assertIn("tab=active", self.hash())
        tabs[0].click()
        self.assertEqual(len(self.all(".projects-project")), 3)
        search = self.wait_for('.projects-controls input[type="search"]')
        search.send_keys("ÇINAR")
        self.wait_until(lambda driver: len(self.all(".projects-project")) == 1)
        self.assertEqual(self.all(".projects-project")[0].get_attribute("data-project"), "cinar")
        saved_hash = self.hash()
        self.driver.refresh()
        self.filled("atlas")
        self.assertEqual(self.hash(), saved_hash)
        self.assertEqual(self.wait_for('.projects-controls input').get_attribute("value"), "ÇINAR")
        search = self.wait_for('.projects-controls input')
        search.clear()
        search.send_keys("missing-project")
        self.wait_for("#projects-list .state")
        self.assertEqual(len(self.all(".projects-project")), 0)
        self.assertIn(self.messages["projects.list.empty"], self.text("#projects-list"))
        self.assertEqual(self.text("#projects-detail-title"), "Atlas")
        self.assert_clean_text()

    def test_unknown_project_keeps_the_list_usable(self) -> None:
        self.open("#/projeler/missing-project")
        self.wait_for('.projects-page[aria-busy="false"] .projects-middle .state')
        self.assertIn(self.messages["projects.project.empty"], self.text(".projects-middle"))
        self.assertEqual(len(self.all(".projects-project")), 2)
        self.wait_for('.projects-project[data-project="atlas"]').click()
        self.filled("atlas")
        self.assert_clean_text()

    def test_long_note_contents_sections_and_expand_all(self) -> None:
        note = self.vault / "notes" / "atlas.md"
        body = '# Atlas\n\nIntroduction.\n\n' + '\n\n'.join(
            f'## Part {index}\n\nBody {index}. [[kavram-bir]]\n\n```text\n## Code heading\n```'
            for index in range(1, 6))
        note.write_text('---\nkind: note\nproject: atlas\n---\n' + body, encoding="utf-8")
        self.restart_server()
        self.open("#/projeler/atlas")
        self.filled("atlas")
        self.assertEqual(self.text("#projects-toc-title"), self.messages["projects.toc"])
        self.assertEqual(len(self.all(".projects-toc li")), 5)
        panels = self.all(".projects-note-section")
        self.assertEqual(len(panels), 5)
        self.assertEqual(self.driver.execute_script("return Array.from(document.querySelectorAll('.projects-note-section'), node => node.open)"),
                         [True, False, False, False, False])
        self.all(".projects-toc a")[-1].click()
        self.assertTrue(self.driver.execute_script("return arguments[0].open", panels[-1]))
        self.assertEqual(self.hash(), "#/projeler/atlas")
        self.wait_for(".projects-expand").click()
        self.assertTrue(self.driver.execute_script("return Array.from(document.querySelectorAll('.projects-note-section')).every(node => node.open)"))
        self.assertEqual(len(self.all(".projects-section-body a.wikilink")), 5)
        self.assert_clean_text()

    def test_layout_and_clean_text(self) -> None:
        self.open("#/projeler/atlas")
        self.filled("atlas")
        self.assert_no_overflow()
        for width in (1280, 1672):
            self.driver.set_window_size(width, 941)
            columns = self.driver.execute_script("return getComputedStyle(document.querySelector('.projects-page')).gridTemplateColumns.split(' ').map(Number.parseFloat)")
            self.assertEqual(columns[0], 360)
            self.assertEqual(columns[-1], 340)
            self.assertEqual(len(columns), 3)
        self.driver.set_window_size(1199, 941)
        self.wait_until(lambda driver: driver.execute_script("return document.querySelector('.projects-right').getBoundingClientRect().top >= document.querySelector('.projects-middle').getBoundingClientRect().bottom"))
        self.assert_no_overflow((1199,))
        self.assertEqual(self.all("#main [style], #main style, #main script"), [])
        self.assert_clean_text()

    def test_project_without_note(self) -> None:
        (self.vault / "notes" / "atlas.md").unlink()
        self.restart_server()
        self.open("#/projeler/atlas")
        self.filled("atlas")
        self.assertIn(self.messages["projects.note.empty"], self.text("#projects-note"))
        self.assertEqual(len(self.all("#projects-tasks .projects-task")), 6)
        self.assert_clean_text()

    def test_request_errors_offer_retry_and_preserve_other_sections(self) -> None:
        for path, selector, retry_path in [
            ("projects", "#projects-list", "projects"),
            ("projects/atlas", ".projects-middle", "projects/atlas"),
            (f'records/{self.golden("project")["note"]["rid"]}', "#projects-note", "records/"),
        ]:
            with self.subTest(path=path):
                self.restart_server()
                original = self.server.api._build

                def fail(request_path: str, *args: Any) -> dict[str, object]:
                    if request_path == path:
                        raise RuntimeError("synthetic_failure")
                    return original(request_path, *args)

                with patch.object(self.server.api, "_build", side_effect=fail):
                    self.open("#/projeler/atlas")
                    retry = self.wait_for(selector + ' [role="alert"] button')
                    self.assertEqual(retry.text, self.messages["action.retry"])
                    if path.startswith("records/"):
                        self.assertEqual(len(self.all("#projects-tasks .projects-task")), 6)
                    errors = self.console_errors()
                    self.assertTrue(errors)
                    self.assertTrue(all("500" in entry["message"] and f"/api/v1/{retry_path}" in entry["message"] for entry in errors), errors)
                retry.click()
                self.filled("atlas")
                self.wait_until(lambda driver: not self.all(selector + ' [role="alert"]'))
                self.assert_clean_text()
