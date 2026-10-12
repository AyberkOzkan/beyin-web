from __future__ import annotations

import os
import shutil
from unittest.mock import patch

from tests.e2e.support import PageTestCase


class MemoryTests(PageTestCase):
    def filled(self) -> None:
        self.wait_for('.memory-page[aria-busy="false"]')

    def shown(self) -> list[str]:
        return [section.get_attribute("id") for section in self.all(".memory-section") if section.is_displayed()]

    def choose(self, section: str) -> None:
        self.wait_for(f'.memory-tabs [data-tab="{section}"]').click()
        self.wait_until(lambda driver: f"bolum={section}" in self.hash())
        self.filled()
        self.assertEqual(self.shown(), [f"memory-{section}"])

    def test_sections_rules_and_scope_filter(self) -> None:
        from selenium.webdriver.support.ui import Select

        memory = self.golden("memory")
        self.open("#/hafiza")
        self.filled()
        self.assertEqual(len(self.all(".memory-section")), 4)
        self.assertIn("Deniz", self.text("#memory-kimlik strong"))
        self.assertIn("Atlas ve Çınar", self.text("#memory-kimlik"))
        # Core.md opens with "# Kimlik"; the card title must not be repeated below itself.
        self.assertEqual(self.text("#memory-kimlik").count(self.messages["memory.identity.title"]), 1)
        self.assertEqual(self.all("#memory-kimlik .memory-markdown h3"), [])
        # Only the chosen section is on screen; the tabs say how much the others hold.
        self.assertEqual(self.shown(), ["memory-kimlik"])
        self.assertEqual(self.text('.memory-tabs [data-tab="kurallar"]'), "Kurallar (3)")
        self.assertEqual(self.text('.memory-tabs [data-tab="konular"]'), "Konular (2)")
        self.assertEqual(self.text('.memory-tabs [data-tab="kimlik"]'), "Kimlik")
        self.choose("kurallar")
        items = memory["rules"]["items"]
        rules = self.all(".memory-rule")
        self.assertEqual(len(rules), len(items))
        self.assertIn(items[2]["text"], rules[2].text)
        self.assertEqual(rules[2].find_elements("css selector", "summary, h3, time, .badge"), [])
        # A rule is one line until it is opened.
        self.assertFalse(rules[0].get_attribute("open"))
        self.assertIn(items[0]["title"], rules[0].text)
        self.assertIn(items[0]["scope"], rules[0].text)
        self.assertNotIn(items[0]["text"], rules[0].text)
        self.assertEqual(self.text(".memory-toggle"), self.messages["memory.expandAll"])
        rules[0].find_element("css selector", "summary").click()
        for key in ("text", "reason", "source"):
            self.assertIn(items[0][key], rules[0].text)
        self.assertEqual(self.text(".memory-toggle"), self.messages["memory.expandAll"])
        self.wait_for(".memory-toggle").click()
        self.assertTrue(rules[1].get_attribute("open"))
        self.assertNotIn(self.messages["memory.reason"], rules[1].text)
        self.assertIn(items[1]["source"], rules[1].text)
        self.assertEqual(self.text(".memory-toggle"), self.messages["memory.collapseAll"])
        self.wait_for(".memory-toggle").click()
        self.assertEqual(self.all(".memory-rule[open]"), [])
        Select(self.wait_for("#memory-scope")).select_by_value("atlas")
        self.wait_until(lambda driver: len(self.all(".memory-rule")) == 1)
        self.assertIn("kapsam=atlas", self.hash())
        self.assertEqual(self.text(".memory-rule h3"), items[0]["title"])
        self.driver.back()
        self.wait_until(lambda driver: len(self.all(".memory-rule")) == 3)
        self.assert_clean_text()

    def test_rules_are_searched_with_turkish_case(self) -> None:
        from selenium.webdriver.support.ui import Select

        items = self.golden("memory")["rules"]["items"]
        self.open("#/hafiza?bolum=kurallar")
        self.filled()
        box = self.wait_for(".memory-search input")
        box.send_keys("KISA")
        self.wait_until(lambda driver: len(self.all(".memory-rule")) == 1)
        self.assertEqual(self.text(".memory-rule h3"), items[1]["title"])
        self.assertEqual(self.text(".memory-rule-count"), self.messages["memory.ruleCount"].format(shown=1, total=3))
        box.send_keys(" atlas")
        self.wait_until(lambda driver: not self.all(".memory-rule"))
        self.assertIn(self.messages["memory.noMatchTitle"], self.text(".memory-rules"))
        self.assertFalse(self.all(".memory-toggle")[0].is_displayed())
        box.clear()
        box.send_keys("kaynağı")
        self.wait_until(lambda driver: len(self.all(".memory-rule")) == 1)
        self.assertEqual(self.text(".memory-rule h3"), items[0]["title"])
        # Choosing a scope redraws the page; what was typed stays.
        Select(self.wait_for("#memory-scope")).select_by_value("genel")
        self.wait_until(lambda driver: "kapsam=genel" in self.hash())
        self.filled()
        self.assertEqual(self.wait_for(".memory-search input").get_attribute("value"), "kaynağı")
        self.assertEqual(self.all(".memory-rule"), [])
        self.choose("kimlik")
        self.choose("kurallar")
        self.assertEqual(self.wait_for(".memory-search input").get_attribute("value"), "")

    def test_session_and_threads(self) -> None:
        memory = self.golden("memory")
        self.open("#/hafiza?bolum=oturum")
        self.filled()
        self.assertEqual(self.shown(), ["memory-oturum"])
        session = memory["last_session"]["card"]
        for value in (session["label"], session["session"], session["items"][0][1]):
            self.assertIn(value, self.text(".memory-session"))
        self.assertEqual(self.text(".memory-session .memory-next-step p"), session["next_step"])
        self.assertEqual(self.all(".memory-session time")[1].get_attribute("datetime"), session["time"])
        self.choose("konular")
        self.assertEqual(len(self.all(".memory-active-threads .memory-thread")), 2)
        first = memory["threads"]["active"][0]
        for key in ("title", "owner", "status", "open", "next_step"):
            self.assertIn(first[key], self.text(".memory-active-threads"))
        self.assertIn("serbest metindir", self.text(".memory-raw"))
        closed = self.wait_for(".memory-closed")
        self.assertFalse(closed.get_attribute("open"))
        self.assertNotIn(memory["threads"]["closed"][0]["title"], closed.text)
        closed.find_element("css selector", "summary").click()
        self.assertIn(memory["threads"]["closed"][0]["title"], closed.text)

    def test_reordered_session_preserves_offline_id(self) -> None:
        path = self.vault / "🔮 850-Companion" / "Last-Session.md"
        original = path.read_text(encoding="utf-8")
        first = original.index("## 2026-01-12")
        second = original.index("## 2026-01-05")
        archive = original.index("## Önceki oturumlar")
        path.write_text(original[:first] + original[second:archive] + original[first:second] + original[archive:], encoding="utf-8")
        self.restart_server()
        self.open("#/hafiza?bolum=oturum")
        self.filled()
        self.assertIn("win-offline", self.text(".memory-session"))
        self.assertIn("codex", self.text(".memory-session"))
        self.assertNotIn("session-cinar-20260112", self.text(".memory-session"))

    def test_unstructured_rules_are_markdown(self) -> None:
        path = self.vault / "🔮 850-Companion" / "Kurallar.md"
        path.write_text("\ufeff# Serbest kurallar\r\n\r\n**Dikkatle oku.**\r\n\r\n- Birinci düşünce\r\n", encoding="utf-8")
        self.restart_server()
        self.open("#/hafiza?bolum=kurallar")
        self.filled()
        self.assertEqual(self.text("#memory-kurallar .markdown-body strong"), "Dikkatle oku.")
        self.assertEqual(self.text("#memory-kurallar .markdown-body li"), "Birinci düşünce")
        self.assertEqual(self.all(".memory-rule, #memory-scope"), [])

    def test_missing_memory_has_one_empty_state(self) -> None:
        directory = (self.vault / "🔮 850-Companion").resolve()
        self.assertEqual(directory.parent, self.vault.resolve())
        shutil.rmtree(directory)
        self.restart_server()
        self.open("#/hafiza")
        self.filled()
        self.assertEqual(len(self.all("#main .state")), 1)
        self.assertIn(self.messages["memory.emptyMessage"], self.text("#main"))
        self.assertEqual(self.all(".memory-section"), [])

    def test_tabs_show_one_section_and_live_in_the_address(self) -> None:
        self.open("#/hafiza")
        self.filled()
        for section in ("kurallar", "oturum", "konular", "kimlik"):
            self.choose(section)
            tab = self.wait_for(f'.memory-tabs [aria-controls="memory-{section}"]')
            self.assertEqual(tab.get_attribute("aria-selected"), "true")
            self.assertEqual(self.wait_for(f"#memory-{section}").get_attribute("role"), "tabpanel")
        self.driver.back()
        self.wait_until(lambda driver: "bolum=konular" in self.hash())
        self.filled()
        self.assertEqual(self.shown(), ["memory-konular"])
        self.open("#/hafiza?bolum=yok")
        self.filled()
        self.assertEqual(self.shown(), ["memory-kimlik"])
        self.assert_no_overflow()

    def test_health_drawer_contents_focus_and_keyboard(self) -> None:
        from selenium.webdriver import ActionChains
        from selenium.webdriver.common.keys import Keys

        health = self.golden("health")
        self.open("#/hafiza")
        self.filled()
        indicator = self.wait_for(".local-status")
        self.assertTrue(indicator.find_elements("css selector", ".tone-active"))
        self.assertEqual(indicator.get_attribute("aria-label"), self.messages["health.indicator.current"])
        indicator.click()
        self.wait_for('.health-drawer[open] .health-body[aria-busy="false"]')
        self.assertIn(health["health_summary"]["installed_version"], self.text(".health-summary"))
        self.assertEqual(self.text(".health-hidden"), self.messages["health.hidden"].replace("{count}", str(health["hidden_private"])))
        self.assertEqual(len(self.all(".health-file")), len(health["health_summary"]["memory_files"]))
        self.assertEqual(len(self.all(".health-file meter")), 2)
        for name, values in health["health_summary"]["memory_files"].items():
            self.assertIn(name, self.text(".health-files"))
            self.assertIn(str(values["chars"]), self.text(".health-files"))
            if values["limit"]:
                self.assertIn(str(values["limit"]), self.text(".health-files"))
        self.assertIn(self.messages["health.warning.frontmatter_unclosed"], self.text(".health-warnings"))
        self.assertIn("notes/bozuk.md", self.text(".health-warnings"))
        self.assert_clean_text(".health-drawer")
        self.assert_no_overflow()
        ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
        self.wait_until(lambda driver: not self.all(".health-drawer[open]"))
        self.assertEqual(self.driver.switch_to.active_element, indicator)
        indicator.send_keys(Keys.ENTER)
        self.wait_for('.health-drawer[open] .health-body[aria-busy="false"]')

    def test_health_drawer_outside_click_and_fetch_on_reopen(self) -> None:
        self.open("#/hafiza")
        self.filled()
        self.driver.execute_script("""
            window.healthRequests = 0;
            const original = window.fetch;
            window.fetch = (...args) => {
                if (String(args[0]).includes('/api/v1/health')) window.healthRequests++;
                return original(...args);
            };
        """)
        for expected in (1, 2):
            self.wait_for(".local-status").click()
            self.wait_for('.health-body[aria-busy="false"]')
            self.assertEqual(self.driver.execute_script("return window.healthRequests"), expected)
            self.driver.execute_script("""
                document.querySelector('.health-drawer').dispatchEvent(
                    new MouseEvent('click', {bubbles: true, clientX: 0, clientY: 0}));
            """)
            self.wait_until(lambda driver: not self.all(".health-drawer[open]"))

    def test_beyin_failure_keeps_memory_working(self) -> None:
        with patch.dict(os.environ, {"FAKE_BEYIN_MODE": "fail"}):
            self.restart_server()
            self.open("#/hafiza")
            self.filled()
            self.assertEqual(len(self.all(".memory-rule")), 3)
            self.assertTrue(self.all(".local-status .tone-waiting"))
            self.wait_for(".local-status").click()
            self.assertEqual(self.text(".health-unavailable"), self.messages["health.unavailable"])
            self.assertIn(str(self.golden("health")["records"]), self.text(".health-interface"))

    def test_memory_error_retry_and_change_refresh(self) -> None:
        self.open("#/hafiza")
        self.filled()
        self.driver.execute_script("""
            const original = window.fetch;
            window.failMemory = true;
            window.fetch = (...args) => {
                if (window.failMemory && String(args[0]).includes('/api/v1/memory')) {
                    return Promise.resolve(new Response(JSON.stringify({error: {code: 'synthetic_failure'}}),
                        {status: 500, headers: {'Content-Type': 'application/json'}}));
                }
                return original(...args);
            };
            document.dispatchEvent(new CustomEvent('beyin:changed'));
        """)
        self.wait_for("#memory-kimlik [role=alert] button")
        self.assertEqual(len(self.all(".memory-section [role=alert]")), 4)
        self.driver.execute_script("window.failMemory = false")
        self.wait_for("#memory-kimlik [role=alert] button").click()
        self.wait_until(lambda driver: len(self.all(".memory-rule")) == 3)
        self.assertEqual(self.all(".memory-section [role=alert]"), [])
        path = self.vault / "🔮 850-Companion" / "Core.md"
        path.write_text("# Updated identity\n\nNew synthetic identity.\n", encoding="utf-8")
        self.driver.execute_script("document.dispatchEvent(new CustomEvent('beyin:changed'))")
        self.wait_until(lambda driver: "New synthetic identity." in self.text("#memory-kimlik"))

    def test_health_error_retry_and_late_response_after_close(self) -> None:
        self.open("#/hafiza")
        self.filled()
        self.driver.execute_script("""
            const original = window.fetch;
            window.healthMode = 'error';
            window.fetch = (...args) => {
                if (!String(args[0]).includes('/api/v1/health')) return original(...args);
                if (window.healthMode === 'error') {
                    return Promise.resolve(new Response(JSON.stringify({error: {code: 'synthetic_failure'}}),
                        {status: 500, headers: {'Content-Type': 'application/json'}}));
                }
                if (window.healthMode === 'hold') {
                    return new Promise(resolve => { window.releaseHealth = () => original(...args).then(resolve); });
                }
                return original(...args);
            };
        """)
        self.wait_for(".local-status").click()
        self.wait_for(".health-body [role=alert] button")
        self.driver.execute_script("window.healthMode = 'ok'")
        self.wait_for(".health-body [role=alert] button").click()
        self.wait_for(".health-files")
        self.wait_for(".health-drawer .icon-button").click()
        self.wait_until(lambda driver: not self.all(".health-drawer[open]"))
        self.driver.execute_script("window.healthMode = 'hold'")
        self.wait_for(".local-status").click()
        self.wait_for(".health-body .skeleton")
        self.wait_until(lambda driver: driver.execute_script("return Boolean(window.releaseHealth)"))
        self.wait_for(".health-drawer .icon-button").click()
        self.wait_until(lambda driver: not self.all(".health-drawer[open]"))
        self.driver.execute_script("window.releaseHealth(); window.healthMode = 'ok'")
        self.wait_for(".local-status").click()
        self.wait_for(".health-files")
        self.assertEqual(len(self.all(".health-body > .card")), 3)

    def test_layout_and_clean_text(self) -> None:
        self.open("#/hafiza")
        self.filled()
        self.assert_no_overflow()
        self.assert_clean_text()
        self.assertEqual(self.all("#main [style], #main style, #main script"), [])


class PlainMemoryTests(PageTestCase):
    beyin = False

    def test_plain_health_and_gray_indicator(self) -> None:
        self.open("#/hafiza")
        self.wait_for('.memory-page[aria-busy="false"]')
        self.assertEqual(len(self.all(".memory-rule")), 3)
        indicator = self.wait_for(".local-status")
        self.assertTrue(indicator.find_elements("css selector", ".tone-unknown"))
        self.assertEqual(indicator.get_attribute("aria-label"), self.messages["health.indicator.plain"])
        indicator.click()
        self.assertEqual(self.text(".health-plain"), self.messages["health.plain"])
        self.assert_clean_text(".health-drawer")
