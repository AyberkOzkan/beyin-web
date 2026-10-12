from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any

from beyin_web.config import Settings
from beyin_web.http.server import create_server
from beyin_web.runtime.beyin_cli import BeyinRuntime
from beyin_web.vault.scan import MarkdownSource
from tests.support import FIXTURES, make_vault


def cached_edge_driver() -> str | None:
    configured = os.environ.get("SE_EDGEDRIVER")
    if configured and Path(configured).is_file():
        return configured
    installed = shutil.which("msedgedriver")
    if installed:
        return installed
    suffix = ".exe" if os.name == "nt" else ""
    cache = Path.home() / ".cache" / "selenium" / "msedgedriver"
    candidates = sorted(cache.glob(f"**/msedgedriver{suffix}"))
    return str(candidates[-1]) if candidates else None


class BrowserTestCase(unittest.TestCase):
    driver: Any
    base_url: str
    source: MarkdownSource

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if os.environ.get("BEYIN_WEB_E2E") == "0":
            raise unittest.SkipTest("BEYIN_WEB_E2E=0")
        try:
            from selenium import webdriver
            from selenium.webdriver.edge.service import Service
        except ImportError as error:
            raise unittest.SkipTest(f"Selenium unavailable: {error}") from error
        executable = cached_edge_driver()
        if executable is None:
            raise unittest.SkipTest("Local Edge driver unavailable; network downloads are disabled")
        options = webdriver.EdgeOptions()
        if os.environ.get("BEYIN_WEB_E2E_SHOW") != "1":
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1672,941")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-component-update")
        options.add_argument("--no-first-run")
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        try:
            cls.driver = webdriver.Edge(service=Service(executable_path=executable), options=options)
            cls.addClassCleanup(cls.driver.quit)
            cls.driver.set_window_size(1672, 941)
            cls.driver.execute_script("return document.readyState")
        except Exception as error:
            raise unittest.SkipTest(f"Edge could not start: {error}") from error
        temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.addClassCleanup(temporary.cleanup)
        vault = make_vault(Path(temporary.name))
        cls.source = MarkdownSource(vault)
        cls.settings = Settings(vault=vault, port=0, token_enabled=False)
        runtime = BeyinRuntime(vault, script=FIXTURES / "fake_beyin.py")
        cls.server = create_server(cls.settings, cls.source, runtime)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.stop_server)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def stop_server(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()

    def setUp(self) -> None:
        super().setUp()
        # The page left by the previous test may still be polling a server that has stopped;
        # leave it and drop whatever it logged, so each test only answers for its own console.
        self.driver.get("about:blank")
        self.driver.get_log("browser")

    def open(self, hash: str = "#/") -> None:
        self.driver.get(self.base_url + "/" + hash)
        self.wait_for("#shell:not([hidden])")
        self.wait_for("#main h1")

    def wait_for(self, css: str, timeout: float = 5) -> Any:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as conditions
        from selenium.webdriver.support.ui import WebDriverWait
        return WebDriverWait(self.driver, timeout).until(conditions.visibility_of_element_located((By.CSS_SELECTOR, css)))

    def text(self, css: str) -> str:
        return str(self.wait_for(css).text)

    def console_errors(self) -> list[dict[str, Any]]:
        return [entry for entry in self.driver.get_log("browser") if entry["level"] == "SEVERE"]

    def tearDown(self) -> None:
        try:
            self.assertEqual(self.console_errors(), [], "Browser console contains errors or CSP violations")
        finally:
            # Leave the page before the cleanups stop its server and delete its files:
            # a request still in flight would keep a file open, which Windows will not delete.
            self.driver.get("about:blank")
            super().tearDown()


class PageTestCase(BrowserTestCase):
    """A fresh vault copy and server per test, with the clock of the golden files.

    Page tests subclass this: the pages then show exactly what tests/fixtures/golden/*.json
    contains. Set ``beyin = False`` for plain mode and ``display_name`` as needed, or change
    ``self.vault`` and call ``restart_server()``.
    """

    beyin: bool = True
    display_name: str = ""
    read_only: bool = False
    vault: Path
    messages: dict[str, Any]

    def setUp(self) -> None:
        super().setUp()
        temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temporary.cleanup)
        self.vault = make_vault(Path(temporary.name))
        static = Path(__file__).resolve().parents[2] / "beyin_web" / "static"
        self.messages = json.loads((static / "i18n" / "tr.json").read_text(encoding="utf-8"))
        self.driver.set_window_size(1672, 941)
        self._stop_page_server: Any = None
        self.restart_server()
        self.addCleanup(self.stop_page_server)

    def restart_server(self) -> None:
        from scripts.update_golden import NOW, TZ
        self.stop_page_server()
        self.settings = Settings(vault=self.vault, port=0, token_enabled=False, display_name=self.display_name,
                                 read_only=self.read_only)
        self.source = MarkdownSource(self.vault, min_interval=0)
        self.runtime = BeyinRuntime(self.vault, script=FIXTURES / "fake_beyin.py", enabled=self.beyin)
        server = create_server(self.settings, self.source, self.runtime)
        server.api.clock = lambda: NOW
        server.api.tz = TZ
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        self.server = server
        self.base_url = f"http://127.0.0.1:{server.server_address[1]}"

        def stop() -> None:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        self._stop_page_server = stop

    def stop_page_server(self) -> None:
        if self._stop_page_server is not None:
            self._stop_page_server()
            self._stop_page_server = None

    def golden(self, name: str) -> Any:
        return json.loads((FIXTURES / "golden" / f"{name}.json").read_text(encoding="utf-8"))

    def wait_until(self, condition: Any, timeout: float = 5) -> Any:
        from selenium.common.exceptions import StaleElementReferenceException
        from selenium.webdriver.support.ui import WebDriverWait
        # A page that redraws itself can replace an element between finding it and reading it;
        # that is "not yet", not a failure.
        return WebDriverWait(self.driver, timeout, ignored_exceptions=[StaleElementReferenceException]).until(condition)

    def all(self, css: str) -> list[Any]:
        return list(self.driver.find_elements("css selector", css))

    def hash(self) -> str:
        return str(self.driver.execute_script("return location.hash"))

    def assert_no_overflow(self, widths: tuple[int, ...] = (1280, 1672)) -> None:
        for width in widths:
            self.driver.set_window_size(width, 941)
            overflow = self.driver.execute_script(
                "return document.documentElement.scrollWidth - document.documentElement.clientWidth")
            self.assertLessEqual(overflow, 0, f"horizontal overflow at {width}px")
        self.driver.set_window_size(1672, 941)

    def assert_clean_text(self, css: str = "#main") -> None:
        words = self.text(css).split()
        for leaked in ("null", "undefined", "NaN", "[object"):
            self.assertNotIn(leaked, words)
