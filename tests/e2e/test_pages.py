from __future__ import annotations

from tests.e2e.support import PageTestCase


class PageScaffoldTests(PageTestCase):
    """Checks shared by every page; each page package adds its own test module."""

    ROUTES = ("#/", "#/projeler", "#/bilgi", "#/gunlukler", "#/grafik", "#/arama", "#/hafiza")

    def test_every_route_renders_a_heading_without_console_errors(self) -> None:
        for route in self.ROUTES:
            with self.subTest(route=route):
                self.open(route)
                self.assertTrue(self.text("#main h1"))
                self.assert_clean_text()
                self.assertEqual(self.console_errors(), [])

    def test_unknown_route_shows_not_found(self) -> None:
        self.open("#/boyle-bir-sayfa-yok")
        self.assertEqual(self.text("#main h1"), self.messages["page.notFound.title"])

    def test_d3_loads_once_from_the_vendor_directory(self) -> None:
        self.open()
        result = self.driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            import('/static/js/d3.js').then(async module => {
              const first = await module.loadD3();
              const second = await module.loadD3();
              done([typeof first.forceSimulation, first === second,
                    document.querySelectorAll('script[src*="/vendor/d3-"]').length]);
            }).catch(error => done([String(error)]));
        """)
        self.assertEqual(result, ["function", True, 4])
