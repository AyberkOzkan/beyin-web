from __future__ import annotations

import http.client

from tests.e2e.support import PageTestCase

GUIDES = "https://github.com/avenoxai/avenoxbeyin/blob/main/docs/v3/"


class SettingsTests(PageTestCase):
    read_only = True

    def open_settings(self) -> None:
        self.open()
        self.wait_for(".settings-button").click()
        self.wait_for(".settings-drawer[open]")

    def test_drawer_offers_language_and_points_to_beyin_guides(self) -> None:
        self.open_settings()
        self.assertEqual(self.text("#settings-title"), self.messages["shell.settings"])
        pressed = {button.get_attribute("data-language"): button.get_attribute("aria-pressed")
                   for button in self.all(".settings-language")}
        self.assertEqual(pressed, {"tr": "true", "en": "false"})
        links = self.all(".settings-guides a")
        self.assertEqual([link.get_dom_attribute("href") for link in links],
                         [GUIDES + name for name in ("YAKALA.md", "PREFERENCES.md", "UPDATE.md")])
        for link in links:
            self.assertEqual((link.get_attribute("target"), link.get_attribute("rel")), ("_blank", "noopener noreferrer"))
        self.assertEqual(links[0].text, self.messages["settings.beyin.capture"])
        self.assert_clean_text(".settings-drawer")
        from selenium.webdriver import ActionChains
        from selenium.webdriver.common.keys import Keys
        ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
        self.wait_until(lambda driver: not self.all(".settings-drawer[open]"))
        self.assertEqual(self.driver.switch_to.active_element.get_attribute("class"), "icon-button settings-button")

        self.wait_for(".settings-button").click()
        self.wait_for('.settings-language[data-language="en"]').click()
        self.wait_until(lambda driver: driver.execute_script("return document.documentElement.lang") == "en")
        self.wait_for("#main h1")
        self.wait_for(".settings-button").click()
        self.assertEqual(self.text("#settings-title"), "Settings")
        self.assertEqual(self.wait_for('.settings-language[data-language="en"]').get_attribute("aria-pressed"), "true")

    def test_closing_the_interface_asks_first_then_stops_the_server(self) -> None:
        self.open_settings()
        self.wait_for(".settings-stop-button").click()
        self.assertEqual(self.text(".settings-confirm p"), self.messages["settings.stop.confirm"])
        self.all(".settings-confirm button")[1].click()
        self.wait_for(".settings-stop-button").click()
        self.wait_for(".settings-danger").click()
        self.assertEqual(self.text("#stopped-screen h1"), self.messages["settings.stopped.title"])
        self.assertIn(self.messages["settings.stopped.message"], self.text("#stopped-screen"))
        self.assertFalse(self.driver.find_element("id", "shell").is_displayed())
        self.assertEqual(self.all(".settings-drawer[open]"), [])

        def stopped(driver: object) -> bool:
            connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=1)
            try:
                connection.request("GET", "/api/v1/pulse")
                connection.getresponse().read()
            except OSError:
                return True
            finally:
                connection.close()
            return False

        self.wait_until(stopped)


class PointerTests(PageTestCase):
    def cursor(self, css: str) -> str:
        return str(self.driver.execute_script("return getComputedStyle(document.querySelector(arguments[0])).cursor", css))

    def choice(self) -> str:
        return str(self.driver.execute_script("return document.documentElement.dataset.cursor"))

    def test_dark_pointer_is_the_default_and_settings_give_the_system_one_back(self) -> None:
        self.open()
        self.assertEqual(self.choice(), "ink")
        self.assertIn("/static/cursor/arrow.svg", self.cursor("#main"))
        self.assertIn("/static/cursor/hand.svg", self.cursor(".nav-link"))
        self.assertIn("/static/cursor/hand.svg", self.cursor(".settings-button"))
        served = self.driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            Promise.all(['arrow', 'hand'].map(name => fetch(`/static/cursor/${name}.svg`).then(response =>
              [response.status, response.headers.get('Content-Type')]))).then(done, error => done(String(error)));
        """)
        self.assertEqual(served, [[200, "image/svg+xml"], [200, "image/svg+xml"]])
        self.open("#/grafik")
        self.wait_for(".graph-canvas")
        self.assertEqual(self.cursor(".graph-canvas"), "grab")

        self.wait_for(".settings-button").click()
        self.wait_for(".settings-drawer[open]")
        self.assertEqual(self.wait_for('.settings-cursor[data-cursor="ink"]').get_attribute("aria-pressed"), "true")
        self.wait_for('.settings-cursor[data-cursor="system"]').click()
        self.assertEqual(self.choice(), "system")
        self.assertEqual(self.wait_for('.settings-cursor[data-cursor="system"]').get_attribute("aria-pressed"), "true")
        self.assertEqual(self.wait_for('.settings-cursor[data-cursor="ink"]').get_attribute("aria-pressed"), "false")
        self.assertEqual((self.cursor("#main"), self.cursor(".nav-link")), ("auto", "pointer"))
        self.driver.refresh()
        self.wait_for("#main h1")
        self.assertEqual(self.choice(), "system")
        self.assertEqual(self.cursor(".nav-link"), "pointer")
        self.wait_for(".settings-button").click()
        self.wait_for('.settings-cursor[data-cursor="ink"]').click()
        self.assertIn("/static/cursor/arrow.svg", self.cursor("#main"))
