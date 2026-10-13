from __future__ import annotations

from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse

from beyin_web.vault.records import make_rid
from tests.e2e.support import PageTestCase


class KnowledgeTests(PageTestCase):
    beyin = False

    def open_record(self, path: str, prefix: str = "not") -> str:
        rid = make_rid(path)
        self.open(f"#/{prefix}/{rid}")
        self.wait_for(f'.record-reader[data-rid="{rid}"]')
        self.wait_for(".context-panel .context-fields")
        return rid

    def assert_expected_http_error(self, status: int, path: str) -> None:
        errors = self.console_errors()
        self.assertTrue(errors)
        self.assertTrue(all(str(status) in entry["message"] and path in entry["message"] for entry in errors), errors)

    def test_first_note_groups_filter_and_history(self) -> None:
        data = self.golden("knowledge")
        first = data["groups"][0]["records"][0]
        self.open("#/bilgi")
        self.wait_until(lambda driver: self.hash() == "#/bilgi/" + first["rid"])
        self.wait_for(f'.record-reader[data-rid="{first["rid"]}"]')
        groups = self.all(".knowledge-group")
        self.assertEqual([group.get_attribute("data-project") for group in groups],
                         [group["project"] or "" for group in data["groups"]])
        self.assertEqual([item.text for item in self.all(".knowledge-group > summary")],
                         [group["project"] or self.messages["knowledge.general"] for group in data["groups"]])
        self.assertEqual([item.text for item in self.all(".knowledge-list strong")],
                         [record["title"] for group in data["groups"] for record in group["records"]])
        self.assertEqual([item.text for item in self.all(".knowledge-list small")],
                         [record["summary"] for group in data["groups"] for record in group["records"]])
        self.assert_no_overflow()
        self.assert_clean_text()
        field = self.wait_for(".knowledge-sidebar input")
        field.send_keys("atlas")
        self.wait_until(lambda driver: len(self.all(".knowledge-list a")) == 1)
        self.assertIn("?q=atlas", self.hash())
        target = data["groups"][1]["records"][0]["rid"]
        self.wait_for(".knowledge-list a").click()
        self.wait_for(f'.record-reader[data-rid="{target}"]')
        self.driver.back()
        self.wait_for(f'.record-reader[data-rid="{first["rid"]}"]')
        self.assertEqual(self.wait_for(".knowledge-sidebar input").get_attribute("value"), "atlas")
        self.driver.refresh()
        self.wait_for(f'.record-reader[data-rid="{first["rid"]}"]')
        self.assertEqual(len(self.all(".knowledge-list a")), 1)

    def test_concept_markdown_and_context(self) -> None:
        rid = self.open_record("knowledge/concepts/kavram-bir.md", "bilgi")
        self.assertIn("Bekliyor", self.text(".reader-body table"))
        self.assertEqual(self.text(".reader-body pre code"), "value = 1")
        checkboxes = self.all('.reader-body input[type="checkbox"]')
        self.assertEqual(len(checkboxes), 2)
        self.assertTrue(all(not checkbox.is_enabled() for checkbox in checkboxes))
        self.assertEqual([checkbox.is_selected() for checkbox in checkboxes], [True, False])
        self.assertEqual(self.text('.context-panel [data-field="project"]'), "atlas")
        atlas = self.golden("record")
        self.assertEqual([link.text for link in self.all(".context-incoming a")], ["index", atlas["title"]])
        self.assertEqual(self.all(".context-outgoing a"), [])
        expected_receipts = [receipt for receipt in atlas["receipts"]
                             if any(ref["rid"] == rid for ref in receipt["refs"])]
        self.assertEqual([item.text for item in self.all(".context-receipts strong")],
                         [receipt["summary"] for receipt in expected_receipts])
        self.assert_no_overflow()
        self.assert_clean_text()

    def test_atlas_context_matches_golden(self) -> None:
        self.open_record("notes/atlas.md")
        record = self.golden("record")
        for direction in ("outgoing", "incoming"):
            key = "links_out" if direction == "outgoing" else "links_in"
            self.assertEqual([link.text for link in self.all(f".context-{direction} a")],
                             [note["title"] for note in record[key]])
            self.assertEqual([link.get_attribute("href").split("#")[-1] for link in self.all(f".context-{direction} a")],
                             ["/not/" + note["rid"] for note in record[key]])
        self.assertEqual([item.text for item in self.all(".context-unresolved span")], record["unresolved"])
        self.assertEqual([item.text for item in self.all(".context-receipts strong")],
                         [receipt["summary"] for receipt in record["receipts"]])
        for link, receipt in zip(self.all(".context-receipts a"), record["receipts"]):
            self.assertTrue(link.get_attribute("href").endswith("#/gunlukler/" + receipt["time"][:10]))
        self.wait_for(".context-receipts a").click()
        self.wait_until(lambda driver: self.hash() == "#/gunlukler/" + record["receipts"][0]["time"][:10])

    def test_wikilinks_aliases_headings_and_private_targets(self) -> None:
        cases = [("kavram-bir", "knowledge/concepts/kavram-bir.md"),
                 ("ikinci aşama", "tasks/atlas-a2.md"),
                 ("kavram-iki#Bölüm", "knowledge/concepts/kavram-iki.md")]
        for label, path in cases:
            self.open_record("notes/atlas.md")
            links = self.all(".reader-body a.wikilink")
            next(link for link in links if link.text == label).click()
            rid = make_rid(path)
            self.wait_until(lambda driver: self.hash() == "#/not/" + rid)
            self.wait_for(f'.record-reader[data-rid="{rid}"]')
        self.open_record("notes/atlas.md")
        unresolved = self.all(".reader-body .wikilink-unresolved")
        self.assertEqual({item.text for item in unresolved}, {"gizli", "olmayan-not"})
        self.assertTrue(all(item.tag_name == "span" for item in unresolved))
        self.assertTrue(self.driver.execute_script("""
            return [...document.querySelectorAll('.reader-body .wikilink-unresolved')].every(node =>
              !node.closest('a') && getComputedStyle(node).color ===
              getComputedStyle(document.querySelector('.reader-metadata time')).color);
        """))
        self.assertEqual(self.text(".reader-body pre code"), "[[kod-icinde]]")
        self.assertEqual(self.all(".reader-body pre a"), [])
        self.assertNotIn("GIZLI-SIZINTI-ISARETI", self.driver.page_source)
        self.assert_no_overflow()
        self.assert_clean_text()

    def test_untrusted_content_stays_text_and_resources_are_local(self) -> None:
        note = self.vault / "notes" / "güvenilmez.md"
        body = note.read_text(encoding="utf-8")
        note.write_text(body.replace("alert(1)", "window.__untrustedExecuted = true"), encoding="utf-8")
        self.open_record("notes/güvenilmez.md")
        self.wait_for(".mini-graph-empty")
        self.assertEqual(self.text(".reader-untrusted"), self.messages["knowledge.untrusted"])
        self.assertIn("<script>window.__untrustedExecuted = true</script>", self.text(".reader-body"))
        self.assertIsNone(self.driver.execute_script("return window.__untrustedExecuted"))
        # The page's own drawing is the only picture; nothing from the note becomes an image or a script.
        self.assertEqual(self.all("#main img:not(.illustration), #main script"), [])
        self.assertEqual(self.all(".reader-body img, .record-reader img"), [])
        resources = self.driver.execute_script("return performance.getEntriesByType('resource').map(entry => entry.name)")
        self.assertTrue(resources)
        self.assertTrue(all(urlparse(url).hostname == "127.0.0.1" for url in resources), resources)
        self.assert_no_overflow()
        self.assert_clean_text()

    def test_task_metadata_precedes_closed_body(self) -> None:
        self.open_record("tasks/atlas-a3.md")
        self.assertEqual(self.text('.reader-task [data-field="status"]'), self.messages["status.active"])
        self.assertEqual(self.text('.reader-task [data-field="owner"]'), "Deniz")
        self.assertEqual(self.text('.reader-task [data-field="next_action"]'), "İkinci örneği doğrula.")
        details = self.wait_for(".reader-task-body")
        self.assertIsNone(details.get_attribute("open"))
        self.assertTrue(all(not item.is_displayed() for item in self.all(".reader-task-body input")))
        self.wait_for(".reader-task-body > summary").click()
        self.wait_for(".reader-task-body .task-checkbox")
        checkboxes = self.all(".reader-task-body input")
        self.assertEqual(len(checkboxes), 4)
        self.assertTrue(all(item.is_displayed() and not item.is_enabled() for item in checkboxes))
        self.assert_no_overflow()
        self.assert_clean_text()

    def test_mini_graph_pixels_click_settle_and_destroy(self) -> None:
        rid = self.open_record("notes/atlas.md")
        canvas = self.wait_for(".mini-graph canvas")
        self.wait_until(lambda driver: driver.execute_script("""
            const canvas = arguments[0];
            return canvas.width > 0 && canvas.height > 0 &&
              canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data.some(value => value > 0);
        """, canvas))
        self.assertTrue(self.driver.execute_script("""
            const canvas = arguments[0];
            return Math.abs(canvas.width - canvas.clientWidth * devicePixelRatio) <= 1 &&
              Math.abs(canvas.height - canvas.clientHeight * devicePixelRatio) <= 1;
        """, canvas))
        self.wait_for(".mini-graph[data-running='false']")
        self.driver.execute_script("""
            const canvas = arguments[0], bounds = canvas.getBoundingClientRect();
            canvas.dispatchEvent(new MouseEvent('click', {bubbles: true,
              clientX: bounds.left + bounds.width / 2, clientY: bounds.top + bounds.height / 2}));
        """, canvas)
        self.wait_until(lambda driver: self.hash() == "#/not/" + rid)
        self.driver.execute_script("window.__oldMiniGraph = document.querySelector('.mini-graph')")
        self.assertTrue(self.wait_for(".context-graph-link").get_attribute("href").endswith("#/grafik?odak=" + rid))
        self.wait_for(".context-graph-link").click()
        self.wait_until(lambda driver: self.hash() == "#/grafik?odak=" + rid)
        self.wait_until(lambda driver: driver.execute_script("return __oldMiniGraph.dataset.destroyed === 'true'"))
        self.assertEqual(self.driver.execute_script("return __oldMiniGraph.dataset.running"), "false")
        unchanged = self.driver.execute_async_script("""
            const done = arguments[arguments.length - 1], before = __oldMiniGraph.dataset.draws;
            requestAnimationFrame(() => requestAnimationFrame(() => done(before === __oldMiniGraph.dataset.draws)));
        """)
        self.assertTrue(unchanged)

    def test_unknown_record_has_empty_state(self) -> None:
        self.open("#/not/000000000000")
        self.assertIn(self.messages["knowledge.notFound"], self.text(".knowledge-reader .state"))
        self.assertIn(self.messages["knowledge.noContext"], self.text(".knowledge-context"))
        self.assert_expected_http_error(404, "/api/v1/records/000000000000")
        self.assert_clean_text()

    def test_path_copy_fallback(self) -> None:
        self.open_record("notes/atlas.md")
        self.driver.execute_script("Object.defineProperty(navigator, 'clipboard', {configurable: true, value: undefined})")
        self.wait_for(".reader-menu summary").click()
        self.wait_for(".reader-menu button").click()
        field = self.wait_for(".reader-path")
        self.assertEqual(field.get_attribute("value"), "notes/atlas.md")
        self.assertEqual(self.driver.execute_script("return arguments[0].selectionEnd - arguments[0].selectionStart", field), len("notes/atlas.md"))

    def test_path_copy_uses_clipboard(self) -> None:
        self.open_record("notes/atlas.md")
        self.driver.execute_script("""
            Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {
              writeText: async text => {window.__copiedPath = text;}
            }});
        """)
        self.wait_for(".reader-menu summary").click()
        self.wait_for(".reader-menu button").click()
        self.wait_until(lambda driver: driver.execute_script("return window.__copiedPath") == "notes/atlas.md")
        self.assertEqual(self.text(".record-reader [role='status']"), self.messages["knowledge.copied"])

    def test_record_and_graph_errors_can_retry(self) -> None:
        rid = make_rid("notes/atlas.md")
        for path, selector, loaded in [
            ("records/" + rid, ".knowledge-reader [role='alert'] button", ".record-reader"),
            ("graph", ".mini-graph [role='alert'] button", ".mini-graph canvas"),
        ]:
            with self.subTest(path=path):
                # A fresh server gives a new origin: neither the server's response cache nor
                # the page left over from the previous case can hide the injected failure.
                self.restart_server()
                original = self.server.api._build

                def fail(*args: Any, **kwargs: Any) -> Any:
                    if args[0] == path:
                        raise RuntimeError("synthetic_failure")
                    return original(*args, **kwargs)

                with patch.object(self.server.api, "_build", side_effect=fail):
                    self.open("#/not/" + rid)
                    retry = self.wait_for(selector)
                    self.assertEqual(retry.text, self.messages["action.retry"])
                    self.assert_expected_http_error(500, "/api/v1/" + path)
                retry.click()
                self.wait_for(loaded)

    def test_list_error_retry_and_empty_vault(self) -> None:
        original = self.server.api._build

        def fail_knowledge(*args: Any, **kwargs: Any) -> Any:
            if args[0] == "knowledge":
                raise RuntimeError("synthetic_failure")
            return original(*args, **kwargs)

        with patch.object(self.server.api, "_build", side_effect=fail_knowledge):
            self.open("#/bilgi")
            retry = self.wait_for(".knowledge-list [role='alert'] button")
            self.assertEqual(retry.text, self.messages["action.retry"])
            self.assert_expected_http_error(500, "/api/v1/knowledge")
        retry.click()
        first = self.golden("knowledge")["groups"][0]["records"][0]
        self.wait_for(f'.record-reader[data-rid="{first["rid"]}"]')
        for note in (self.vault / "knowledge" / "concepts").glob("*.md"):
            note.unlink()
        self.restart_server()
        self.open("#/bilgi")
        self.assertIn(self.messages["knowledge.emptyMessage"], self.text(".knowledge-reader .state"))
        self.assertIn(self.messages["knowledge.noContext"], self.text(".knowledge-context"))

    def test_vault_change_refreshes_reader(self) -> None:
        self.open_record("notes/atlas.md")
        note = self.vault / "notes" / "atlas.md"
        note.write_text(note.read_text(encoding="utf-8") + "\nSynthetic update.\n", encoding="utf-8")
        self.driver.execute_script("document.dispatchEvent(new CustomEvent('beyin:changed'))")
        self.wait_until(lambda driver: "Synthetic update." in driver.find_element("css selector", ".reader-body").text)
        self.assert_clean_text()
