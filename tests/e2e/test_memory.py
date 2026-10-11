from __future__ import annotations

import os
import shutil
from unittest.mock import patch

from tests.e2e.support import PageTestCase


class MemoryTests(PageTestCase):
    def filled(self) -> None:
        self.wait_for('.memory-page[aria-busy="false"]')

    def test_sections_rules_and_scope_filter(self) -> None:
        from selenium.webdriver.support.ui import Select

        memory = self.golden("memory")
        self.open("#/hafiza")
        self.filled()
        self.assertEqual(len(self.all(".memory-section")), 4)
        self.assertIn("Deniz", self.text("#memory-kimlik strong"))
        self.assertIn("Atlas ve Çınar", self.text("#memory-kimlik"))
        rules = self.all(".memory-rule")
        self.assertEqual(len(rules), len(memory["rules"]["items"]))
        self.assertIn(memory["rules"]["items"][2]["text"], rules[2].text)
        self.assertEqual(rules[2].find_elements("css selector", "details, h3, time, .badge"), [])
        reason = rules[0].find_element("css selector", "details")
        self.assertFalse(reason.get_attribute("open"))
        reason.find_element("css selector", "summary").click()
        self.assertIn(memory["rules"]["items"][0]["reason"], reason.text)
        self.assertIn(memory["rules"]["items"][0]["source"], reason.text)
        second = rules[1].find_element("css selector", "details")
        second.find_element("css selector", "summary").click()
        self.assertNotIn(self.messages["memory.reason"], second.text)
        self.assertIn(memory["rules"]["items"][1]["source"], second.text)
        Select(self.wait_for("#memory-scope")).select_by_value("atlas")
        self.wait_until(lambda driver: len(self.all(".memory-rule")) == 1)
        self.assertIn("kapsam=atlas", self.hash())
        self.assertEqual(self.text(".memory-rule h3"), memory["rules"]["items"][0]["title"])
        self.driver.back()
        self.wait_until(lambda driver: len(self.all(".memory-rule")) == 3)
        self.assert_clean_text()

    def test_session_and_threads(self) -> None:
        memory = self.golden("memory")
        self.open("#/hafiza")
        self.filled()
        session = memory["last_session"]["card"]
        for value in (session["label"], session["session"], session["items"][0][1]):
            self.assertIn(value, self.text(".memory-session"))
        self.assertEqual(self.text(".memory-session .memory-next-step p"), session["next_step"])
        self.assertEqual(self.all(".memory-session time")[1].get_attribute("datetime"), session["time"])
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

    def test_tabs_update_address_scroll_and_back(self) -> None:
        self.open("#/hafiza")
        self.filled()
        for section in ("kurallar", "oturum", "konular", "kimlik"):
            self.wait_for(f'.memory-tabs [aria-controls="memory-{section}"]').click()
            self.wait_until(lambda driver: f"bolum={section}" in self.hash())
            self.filled()
            self.wait_until(lambda driver: driver.execute_script(
                """
                const section = document.querySelector(arguments[0]);
                const target = Math.max(0, section.getBoundingClientRect().top + scrollY - 24);
                const maximum = document.documentElement.scrollHeight - innerHeight;
                return Math.abs(scrollY - Math.min(target, maximum)) < 2;
                """,
                f"#memory-{section}"))
            self.assertEqual(self.wait_for(f'.memory-tabs [aria-controls="memory-{section}"]').get_attribute("aria-selected"), "true")
        self.driver.back()
        self.wait_until(lambda driver: "bolum=konular" in self.hash())
        self.filled()

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
        self.wait_for(".memory-rule")
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
