from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any
from unittest.mock import patch

from beyin_web.config import Settings
from beyin_web.http.server import create_server
from beyin_web.runtime.beyin_cli import BeyinRuntime
from beyin_web.vault.scan import MarkdownSource
from scripts.update_golden import NOW, TZ
from tests.e2e.support import BrowserTestCase
from tests.support import FIXTURES, make_vault


class HomeTests(BrowserTestCase):
    def setUp(self) -> None:
        super().setUp()
        temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = make_vault(self.root)
        self.static_dir = self.root / "static"
        shutil.copytree(Path(__file__).resolve().parents[2] / "beyin_web" / "static", self.static_dir)
        self.settings = Settings(self.vault, port=0, token_enabled=False, display_name="Deniz", static_dir=self.static_dir)
        self.source = MarkdownSource(self.vault, min_interval=0)
        self.runtime = BeyinRuntime(self.vault, enabled=False)
        self.start_home_server()
        self.golden = json.loads((FIXTURES / "golden" / "home.json").read_text(encoding="utf-8"))
        self.messages = json.loads((self.static_dir / "i18n" / "tr.json").read_text(encoding="utf-8"))
        self.driver.set_window_size(1672, 941)

    def start_home_server(self) -> None:
        self.server = create_server(self.settings, self.source, self.runtime)
        self.server.api.clock = lambda: NOW
        self.server.api.tz = TZ
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        server, thread = self.server, self.thread

        def stop() -> None:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        self.addCleanup(stop)

    def filled(self) -> None:
        self.wait_for('.home-page[aria-busy="false"] #home-counts .home-counter')

    def wait_until(self, condition: Any) -> Any:
        from selenium.webdriver.support.ui import WebDriverWait
        return WebDriverWait(self.driver, 5).until(condition)

    def test_all_sections_show_golden_values_and_vault_name(self) -> None:
        self.open()
        self.filled()
        words = self.text("#main").split()
        self.assertNotIn("null", words)
        self.assertNotIn("undefined", words)
        expected = {
            "greeting": self.golden["greeting"]["display_name"],
            "last_session": self.golden["last_session"]["next_step"],
            "recent": self.golden["recent"][0]["title"],
            "projects": self.golden["projects"][0]["name"],
            "threads": self.golden["threads"][0]["title"],
            "tasks": self.golden["tasks"][0]["title"],
            "week": str(self.golden["week"]["changed"]),
            "upcoming": self.golden["upcoming"][0]["record"]["title"],
        }
        for key, value in expected.items():
            with self.subTest(section=key):
                self.assertIn(value, self.text(f"#home-{key}"))
        for key, count in self.golden["counts"].items():
            self.assertEqual(self.text(f'[data-counter="{key}"] .home-number'), str(count["total"]))
        self.assertIn(self.golden["last_session"]["label"], self.text("#home-last_session"))
        self.assertEqual(self.text("#vault-status .vault-name strong"), self.vault.name)
        self.assertEqual(len(self.driver.find_elements("css selector", ".home-chart rect")), 7)
        self.assertEqual(self.driver.find_elements("css selector", "#home-greeting .illustration, #sidebar-art img, [style], style"), [])
        resources = self.driver.execute_script("return performance.getEntriesByType('resource').map(entry => entry.name)")
        self.assertFalse(any("/static/img/" in url for url in resources))

    def test_note_project_and_memory_links(self) -> None:
        cases = [("#home-recent .home-row", "#/not/" + self.golden["recent"][0]["rid"]),
                 ("#home-projects .home-row", "#/projeler/" + self.golden["projects"][0]["name"]),
                 ("#home-last_session .home-session-link", "#/hafiza?bolum=oturum"),
                 ("#home-threads .home-row", "#/hafiza?bolum=konular")]
        for selector, route in cases:
            self.open()
            self.filled()
            self.wait_for(selector).click()
            self.wait_until(lambda driver: driver.current_url.endswith(route))
        for selector, route in [("#home-recent .home-all", "#/bilgi"),
                                ("#home-projects .home-all", "#/projeler"),
                                ("#home-threads .home-all", "#/hafiza?bolum=konular"),
                                ("#home-tasks .home-footer-link", "#/projeler")]:
            self.open()
            self.filled()
            self.assertTrue(self.wait_for(selector).get_attribute("href").endswith(route))

    def test_missing_companion_keeps_empty_sections(self) -> None:
        shutil.rmtree(self.vault / "🔮 850-Companion")
        self.open()
        self.filled()
        for key in ("last_session", "threads"):
            self.assertIn(self.messages[f"home.{key}.empty"], self.text(f"#home-{key}"))
        self.assertIn(self.golden["tasks"][0]["title"], self.text("#home-tasks"))

    def test_error_and_retry(self) -> None:
        with patch.object(self.server.api, "_home", side_effect=RuntimeError("synthetic_failure")):
            self.open()
            retry = self.wait_for(".home-feedback [role=alert] button")
            self.assertEqual(retry.text, self.messages["action.retry"])
            self.assertIn(self.messages["home.error"], self.text(".home-feedback"))
            errors = self.console_errors()
            self.assertTrue(errors)
            self.assertTrue(all("500" in entry["message"] and "/api/v1/home" in entry["message"] for entry in errors), errors)
        retry.click()
        self.filled()
        self.assertEqual(self.driver.find_elements("css selector", ".home-feedback [role=alert]"), [])

    def test_layout_has_no_horizontal_overflow(self) -> None:
        self.open()
        self.filled()
        for width in (1280, 1672):
            self.driver.set_window_size(width, 941)
            self.wait_until(lambda driver: driver.execute_script(
                "return matchMedia('(max-width: 1399px)').matches") == (width == 1280))
            self.wait_until(lambda driver: driver.execute_script("return document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
            columns = self.driver.execute_script("return getComputedStyle(document.querySelector('.home-middle')).gridTemplateColumns.split(' ').length")
            self.assertEqual(columns, 2 if width == 1280 else 3)

    def test_whole_page_fits_one_screen_at_the_mockup_size(self) -> None:
        self.open()
        self.filled()
        self.wait_for("#home-week svg, #home-week .home-empty")
        # Headless Edge takes its window chrome out of the 941px, so the page is measured against the mockup's height.
        bottom = self.driver.execute_script(
            "return document.querySelector('.home-page').getBoundingClientRect().bottom + scrollY"
            " + parseFloat(getComputedStyle(document.getElementById('main')).paddingBottom)")
        self.assertLessEqual(bottom, 941)

    def test_drawing_appears_when_present_at_server_start(self) -> None:
        images = self.static_dir / "img"
        images.mkdir()
        pixel = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGP4DwQACfsD/fteaysAAAAASUVORK5CYII=")
        (images / "hero-palace.png").write_bytes(pixel)
        (images / "sidebar-tree.png").write_bytes(pixel)
        self.start_home_server()
        self.open()
        self.filled()
        for selector, name in (("#home-greeting img", "hero-palace"), ("#sidebar-art img", "sidebar-tree")):
            picture = self.wait_for(selector)
            self.wait_until(lambda driver: driver.execute_script("return arguments[0].complete && arguments[0].naturalWidth > 0", picture))
            self.assertTrue(picture.get_attribute("src").endswith(f"/static/img/{name}.png"))

    def test_no_upcoming_expands_tasks_and_other_empty_sections_remain(self) -> None:
        original = self.server.api._home

        def empty_home(*args: Any) -> dict[str, object]:
            data = original(*args)
            for key in ("recent", "projects", "tasks", "threads", "upcoming"):
                data[key] = []
            data["last_session"] = None
            data["counts"] = {key: {"total": 0, "last_7_days": 0} for key in self.golden["counts"]}
            data["week"] = {"days": {key: 0 for key in self.golden["week"]["days"]}, "receipts": 0, "changed": 0}
            return data

        with patch.object(self.server.api, "_home", side_effect=empty_home):
            self.open()
            self.wait_for('.home-page[aria-busy="false"] #home-tasks .home-empty')
            self.assertEqual(self.driver.find_elements("css selector", "#home-upcoming"), [])
            self.assertTrue(self.driver.find_elements("css selector", ".home-bottom.home-no-upcoming"))
            for key in ("counts", "last_session", "recent", "projects", "threads", "tasks", "week"):
                self.assertIn(self.messages[f"home.{key}.empty"], self.text(f"#home-{key}"))

    def test_changed_event_updates_sections_and_preserves_scroll(self) -> None:
        self.driver.set_window_size(1672, 600)
        self.open()
        self.filled()
        self.driver.execute_script("""
            window.scrollTo(0, 150);
            window.homeBefore = { tasks: document.querySelector('#home-tasks .home-row'),
              recent: document.querySelector('#home-recent .home-row'), scroll: window.scrollY };
        """)
        note = self.vault / "notes" / "new.md"
        note.write_text("# Synthetic fresh note\n", encoding="utf-8")
        os.utime(note, (NOW.timestamp(), NOW.timestamp()))
        self.driver.execute_script("document.dispatchEvent(new CustomEvent('beyin:changed'))")
        self.wait_until(lambda driver: "Synthetic fresh note" in driver.find_element("id", "home-recent").text)
        self.assertTrue(self.driver.execute_script("return homeBefore.tasks === document.querySelector('#home-tasks .home-row')"))
        self.assertFalse(self.driver.execute_script("return homeBefore.recent === document.querySelector('#home-recent .home-row')"))
        self.assertEqual(self.driver.execute_script("return window.scrollY"), self.driver.execute_script("return homeBefore.scroll"))
        self.driver.execute_script("location.hash = '/bilgi'")
        # Read the heading in one script call: the page is being replaced while we look at it.
        self.wait_until(lambda driver: driver.execute_script(
            "return document.querySelector('#main h1')?.textContent") == self.messages["page.knowledge.title"])
        self.driver.execute_script("document.dispatchEvent(new CustomEvent('beyin:changed'))")
        self.assertEqual(self.driver.find_elements("css selector", ".home-page"), [])
