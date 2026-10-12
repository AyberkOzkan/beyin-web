from __future__ import annotations

import threading
from dataclasses import replace

from beyin_web.http.server import create_server
from beyin_web.domain.obsidian import obsidian_uri, obsidian_vault_uri
from beyin_web.vault.records import make_rid
from tests.e2e.support import BrowserTestCase, PageTestCase


class ObsidianShellTests(PageTestCase):
    def test_topbar_targets_vault_record_and_selected_knowledge_note(self) -> None:
        self.open()
        link = self.wait_for(".topbar-actions .obsidian-link")
        self.assertEqual(link.text, self.messages["shell.openObsidian"])
        self.assertEqual(link.get_dom_attribute("href"), obsidian_vault_uri(str(self.vault)))
        self.assertEqual(link.get_attribute("aria-label"), self.messages["shell.openVaultObsidian"])
        path = "notes/atlas.md"
        self.driver.execute_script("location.hash = arguments[0]", "#/not/" + make_rid(path))
        self.wait_for(".record-reader")
        self.wait_until(lambda driver: link.get_dom_attribute("href") == obsidian_uri(str(self.vault), path))
        self.assertEqual(link.get_attribute("aria-label"), self.messages["shell.openRecordObsidian"])
        self.driver.execute_script("location.hash = '#/'")
        self.wait_for('.home-page[aria-busy="false"]')
        self.wait_until(lambda driver: link.get_dom_attribute("href") == obsidian_vault_uri(str(self.vault)))
        path = "knowledge/concepts/kavram-bir.md"
        self.driver.execute_script("location.hash = arguments[0]", "#/bilgi/" + make_rid(path))
        self.wait_for('.record-reader[data-rid="' + make_rid(path) + '"]')
        self.wait_until(lambda driver: link.get_dom_attribute("href") == obsidian_uri(str(self.vault), path))
        self.assertEqual(link.get_attribute("aria-label"), self.messages["shell.openRecordObsidian"])
        self.driver.set_window_size(1024, 941)
        self.wait_until(lambda driver: driver.execute_script("return window.innerWidth <= 1024"))
        self.assertEqual(self.driver.execute_script("""
            const bar = document.querySelector('#topbar');
            return bar.scrollWidth <= bar.clientWidth &&
              [...bar.querySelectorAll('a, button, input')].every(node => {
                const rect = node.getBoundingClientRect(), parent = bar.getBoundingClientRect();
                return rect.left >= parent.left && rect.right <= parent.right;
              });
        """), True)
        self.assertFalse(self.wait_for(".obsidian-link").find_element("css selector", ".obsidian-link-text").is_displayed())
        self.assert_clean_text()
        self.assert_no_overflow((1024,))

    def test_topbar_rejects_invalid_or_missing_record_addresses(self) -> None:
        self.open()
        self.wait_for(".obsidian-link")
        for uri in ("", "https://example.org", "javascript:alert(1)"):
            self.driver.execute_script(
                "document.dispatchEvent(new CustomEvent('beyin:record', {detail: {obsidianUri: arguments[0]}}))", uri)
            self.wait_until(lambda driver: not self.all(".obsidian-link"))
        self.driver.execute_script(
            "document.dispatchEvent(new CustomEvent('beyin:record', {detail: {obsidianUri: null}}))")
        self.assertEqual(self.wait_for(".obsidian-link").get_dom_attribute("href"), obsidian_vault_uri(str(self.vault)))


class ShellTests(BrowserTestCase):
    def test_navigation(self) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        self.open()
        links = self.driver.find_elements(By.CSS_SELECTOR, ".nav-link")
        self.assertEqual([link.text for link in links], ["Ana Sayfa", "Projeler", "Bilgi", "Günlükler", "Grafik", "Arama", "Hafıza", "Raporlar"])
        for link, route in zip(links, ["#/", "#/projeler", "#/bilgi", "#/gunlukler", "#/grafik", "#/arama", "#/hafiza", "#/raporlar"]):
            link.click()
            # A page may move on to its first item (#/bilgi -> #/bilgi/{rid}); the menu entry stays current.
            def arrived(driver: object, route: str = route, link: object = link) -> bool:
                current = "#" + driver.current_url.partition("#")[2]
                inside = current == route or (route != "#/" and current.startswith(route + "/"))
                return inside and link.get_attribute("aria-current") == "page"

            WebDriverWait(self.driver, 5).until(arrived)
            if route == "#/":
                self.wait_for('.home-page[aria-busy="false"]')
            else:
                self.assertEqual(self.text("#main h1"), link.text)

    def test_showcase_markdown_and_resources(self) -> None:
        from selenium.webdriver.common.by import By
        self.open("#/_vitrin")
        self.wait_for("#showcase-markdown table")
        self.wait_for("#showcase-markdown pre code")
        boxes = self.driver.find_elements(By.CSS_SELECTOR, "#showcase-markdown input[type=checkbox]")
        self.assertEqual(len(boxes), 2)
        self.assertTrue(all(not box.is_enabled() for box in boxes))
        self.assertFalse(boxes[0].is_selected())
        self.assertTrue(boxes[1].is_selected())
        self.assertTrue(self.driver.find_elements(By.CSS_SELECTOR, '#showcase-markdown a[href^="#/not/"]'))
        self.assertEqual(self.text(".wikilink-unresolved"), "Eksik not")
        self.assertEqual(self.driver.find_elements(By.CSS_SELECTOR, "#showcase-markdown script, #showcase-markdown img, [style], style"), [])
        self.assertFalse(self.driver.execute_script("return Boolean(window.__markdownExecuted)"))
        resources = self.driver.execute_script("return performance.getEntriesByType('resource').map(entry => entry.name)")
        from urllib.parse import urlsplit
        self.assertTrue(resources)
        self.assertTrue(all(urlsplit(url).hostname == "127.0.0.1" for url in resources), resources)

    def test_fonts_and_icons(self) -> None:
        from selenium.webdriver.support.ui import WebDriverWait
        self.open("#/_vitrin")
        loaded = self.driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            Promise.all([
              document.fonts.load('16px "EB Garamond"', 'ğ ı İ ş'),
              document.fonts.load('16px "Source Serif 4"', 'ğ ı İ ş')
            ]).then(fonts => done(fonts.every(group => group.length > 0)), () => done(false));
        """)
        self.assertTrue(loaded)
        self.assertTrue(self.driver.execute_script("return document.fonts.check('16px \"EB Garamond\"', 'ğ ı İ ş') && document.fonts.check('16px \"Source Serif 4\"', 'ğ ı İ ş')"))
        self.assertIn("ğ", self.text("#turkish-sample"))
        self.assertIn("Source Serif 4", self.driver.execute_script("return getComputedStyle(document.getElementById('turkish-sample')).fontFamily"))
        WebDriverWait(self.driver, 5).until(lambda driver: driver.execute_script("return Array.from(document.querySelectorAll('use')).some(use => { const box = use.getBBox(); return box.width > 0 && box.height > 0; })"))

    def test_keyboard_and_health_drawer(self) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver import ActionChains
        self.open()
        search = self.driver.find_element(By.ID, "global-search")
        ActionChains(self.driver).key_down(Keys.CONTROL).send_keys("k").key_up(Keys.CONTROL).perform()
        self.assertEqual(self.driver.switch_to.active_element, search)
        search.send_keys("/")
        self.assertEqual(search.get_attribute("value"), "/")
        self.driver.find_element(By.ID, "main").click()
        ActionChains(self.driver).send_keys("/").perform()
        self.assertEqual(self.driver.switch_to.active_element, search)
        self.driver.find_element(By.CSS_SELECTOR, ".local-status").click()
        self.wait_for(".health-drawer[open]")
        ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
        self.assertFalse(self.driver.find_element(By.CSS_SELECTOR, ".health-drawer").get_attribute("open"))

    def test_vault_status_uses_pulse(self) -> None:
        self.open()
        records = self.wait_for("#vault-records")
        count = len(self.source.snapshot().records)
        self.assertEqual(records.get_attribute("data-count"), str(count))
        self.assertEqual(records.text, f"{count} kayıt")

    def test_token_entry_and_api_unauthorized(self) -> None:
        from selenium.webdriver.support.ui import WebDriverWait
        token = "e2e_session_secret"
        settings = replace(self.settings, token_enabled=True, token=token)
        server = create_server(settings, self.source, self.server.runtime)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        address = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            self.driver.delete_all_cookies()
            self.driver.get(address + "/")
            self.assertIn("terminalde", self.text("body"))
            self.assertTrue(all("401" in entry["message"] for entry in self.console_errors()))
            self.driver.get(address + "/?t=" + token)
            self.wait_for("#shell:not([hidden])")
            self.wait_for("#vault-records")
            self.assertNotIn(token, self.driver.current_url)
            self.assertNotIn("?t=", self.driver.current_url)
            self.assertEqual(self.console_errors(), [])
            self.driver.delete_all_cookies()
            self.driver.execute_script("import('/static/js/api.js').then(api => api.get('/api/v1/pulse').catch(() => {}))")
            WebDriverWait(self.driver, 5).until(lambda driver: driver.find_elements("css selector", "#login-screen"))
            self.assertIn("terminalde", self.text("#login-screen"))
            self.assertTrue(all("401" in entry["message"] for entry in self.console_errors()))
        finally:
            self.driver.get("about:blank")
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
