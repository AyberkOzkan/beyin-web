from __future__ import annotations

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
        if os.environ.get("BEYIN_WEB_E2E_GOSTER") != "1":
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
        temporary = tempfile.TemporaryDirectory()
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
            super().tearDown()
