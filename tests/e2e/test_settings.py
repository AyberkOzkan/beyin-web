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
