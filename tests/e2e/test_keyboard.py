from __future__ import annotations

from beyin_web.domain.obsidian import obsidian_uri
from beyin_web.vault.records import make_rid
from tests.e2e.support import PageTestCase


class KeyboardTests(PageTestCase):
    def keys(self, *keys: str) -> None:
        from selenium.webdriver import ActionChains
        ActionChains(self.driver).send_keys(*keys).perform()

    def active_id(self) -> str:
        return str(self.driver.execute_script("return document.activeElement.id"))

    def assert_focus_ring(self) -> None:
        self.assertTrue(self.driver.execute_script("""
            let node = document.activeElement;
            if (!node || !node.getClientRects().length) return false;
            while (node && node !== document.body) {
              const style = getComputedStyle(node);
              if (style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0 &&
                  (node === document.activeElement || node.matches(':focus-within'))) return true;
              node = node.parentElement;
            }
            return false;
        """), "The focused control has no visible focus ring")

    def test_skip_content_is_first_tab_stop(self) -> None:
        from selenium.webdriver.common.keys import Keys
        self.open()
        self.wait_for('.home-page[aria-busy="false"]')
        self.keys(Keys.TAB)
        self.assertEqual(self.active_id(), "skip-content")
        self.assertEqual(self.driver.switch_to.active_element.text, self.messages["shell.skipContent"])
        self.assert_focus_ring()
        self.keys(Keys.ENTER)
        self.assertEqual(self.active_id(), "main")
        self.assertEqual(self.hash(), "#/")

    def test_navigation_arrows_wrap_and_enter_focuses_main(self) -> None:
        from selenium.webdriver.common.keys import Keys
        self.open()
        self.wait_for('.home-page[aria-busy="false"]')
        self.keys(Keys.TAB, Keys.TAB, Keys.TAB)
        links = self.all("#navigation a")
        self.assertEqual(self.driver.switch_to.active_element, links[0])
        for key, index in [(Keys.ARROW_DOWN, 1), (Keys.ARROW_UP, 0), (Keys.ARROW_UP, 6),
                           (Keys.ARROW_DOWN, 0), (Keys.END, 6), (Keys.HOME, 0), (Keys.ARROW_DOWN, 1)]:
            self.keys(key)
            self.assertEqual(self.driver.switch_to.active_element, links[index])
            self.assert_focus_ring()
        self.keys(Keys.ENTER)
        self.wait_for('.projects-page[aria-busy="false"]')
        self.assertEqual(self.text("#main h1"), self.messages["page.projects.title"])
        self.assertEqual(self.active_id(), "main")

    def test_home_record_and_back_without_mouse(self) -> None:
        from selenium.webdriver.common.keys import Keys
        self.open()
        self.wait_for('.home-page[aria-busy="false"]')
        reached = False
        for _ in range(80):
            self.keys(Keys.TAB)
            self.assert_focus_ring()
            href = self.driver.switch_to.active_element.get_dom_attribute("href") or ""
            if href.startswith("#/not/"):
                reached = True
                break
        self.assertTrue(reached, "No record link was reached in 80 Tab presses")
        self.keys(Keys.ENTER)
        self.wait_for(".record-reader .reader-body")
        self.assertEqual(self.active_id(), "main")
        self.driver.back()
        self.wait_for('.home-page[aria-busy="false"]')
        self.assertEqual(self.hash(), "#/")
        self.assertEqual(self.active_id(), "main")
        self.assertTrue(self.all('#home-recent a[href^="#/not/"]'))

    def test_project_tabs_keep_focus_on_selected_tab(self) -> None:
        from selenium.webdriver.common.keys import Keys
        self.open("#/projeler")
        self.wait_for('.projects-page[aria-busy="false"]')
        first = self.wait_for('.projects-controls [role="tab"][aria-selected="true"]')
        first.send_keys(Keys.ARROW_RIGHT)
        selected = self.wait_for('.projects-controls [data-tab="active"][aria-selected="true"]')
        self.assertEqual(self.driver.switch_to.active_element, selected)
        self.assert_focus_ring()
        selected.send_keys(Keys.ARROW_LEFT)
        self.assertEqual(self.driver.switch_to.active_element, first)

    def test_record_menu_uri_escape_and_outside_click(self) -> None:
        from selenium.webdriver.common.keys import Keys
        self.open("#/not/" + make_rid("notes/atlas.md"))
        toggle = self.wait_for(".reader-menu summary")
        toggle.send_keys(Keys.ENTER)
        self.wait_for(".reader-menu[open] button")
        link = self.wait_for('.reader-menu a[href^="obsidian://open?"]')
        self.assertEqual(link.text, self.messages["knowledge.openObsidian"])
        self.assertEqual(link.get_dom_attribute("href"), obsidian_uri(str(self.vault), "notes/atlas.md"))
        self.keys(Keys.TAB)
        self.assertEqual(self.driver.switch_to.active_element, self.wait_for(".reader-menu button"))
        self.assert_focus_ring()
        self.keys(Keys.TAB)
        self.assertEqual(self.driver.switch_to.active_element, link)
        self.assert_focus_ring()
        self.keys(Keys.ESCAPE)
        self.assertEqual(self.all(".reader-menu[open]"), [])
        self.assertEqual(self.driver.switch_to.active_element, toggle)
        self.assertFalse(link.is_displayed())
        self.keys(Keys.TAB)
        self.assertNotEqual(self.driver.switch_to.active_element, link)
        self.assertNotEqual(self.driver.switch_to.active_element, self.all(".reader-menu button")[0])
        toggle.send_keys(Keys.ENTER)
        self.wait_for(".reader-menu[open]")
        self.wait_for("#main h1").click()
        self.assertEqual(self.all(".reader-menu[open]"), [])

    def test_same_page_and_vault_refresh_preserve_focus(self) -> None:
        from selenium.webdriver.common.keys import Keys
        self.open("#/hafiza")
        self.wait_for('.memory-page[aria-busy="false"]')
        first = self.wait_for('.memory-tabs [aria-selected="true"]')
        first.send_keys(Keys.ARROW_RIGHT)
        self.wait_for('.memory-page[aria-busy="false"]')
        self.wait_until(lambda driver: driver.execute_script("return document.activeElement.dataset.tab") == "kurallar")
        self.assert_focus_ring()
        self.wait_for("#memory-scope")
        self.driver.execute_script("document.querySelector('#memory-scope').focus(); document.dispatchEvent(new CustomEvent('beyin:changed'))")
        self.wait_for('.memory-page[aria-busy="false"]')
        self.wait_until(lambda driver: self.active_id() == "memory-scope")

    def test_search_sets_its_own_focus_after_page_transition(self) -> None:
        from selenium.webdriver.common.keys import Keys
        self.open()
        self.keys(Keys.TAB, Keys.TAB, Keys.TAB, Keys.END, Keys.ARROW_UP, Keys.ENTER)
        self.wait_for("#search-query")
        self.assertEqual(self.active_id(), "search-query")
        self.assert_focus_ring()

    def test_pages_have_named_controls_and_consistent_headings(self) -> None:
        cases = [("#/", '.home-page[aria-busy="false"]'), ("#/projeler", '.projects-page[aria-busy="false"]'),
                 ("#/bilgi", ".record-reader"), ("#/gunlukler", '.journal-page[aria-busy="false"]'),
                 ("#/grafik", ".graph-canvas"), ("#/arama", ".search-results .state"),
                 ("#/hafiza", '.memory-page[aria-busy="false"]'),
                 ("#/not/" + make_rid("notes/atlas.md"), ".record-reader")]
        for address, loaded in cases:
            with self.subTest(address=address):
                self.open(address)
                self.wait_for(loaded)
                self.assertEqual(len(self.all("#main h1")), 1)
                self.assertTrue(self.driver.execute_script("""
                    const visible = node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
                    return [...document.querySelectorAll('button, a')].filter(visible).every(node =>
                      node.innerText.trim() || node.getAttribute('aria-label')?.trim() || node.title.trim());
                """))
                self.assertTrue(self.driver.execute_script("""
                    let previous = 0;
                    return [...document.querySelectorAll('#main h1, #main h2, #main h3, #main h4, #main h5, #main h6')]
                      .filter(node => node.getClientRects().length).every(node => {
                        const level = Number(node.tagName.slice(1)), valid = level <= previous + 1;
                        previous = level; return valid;
                      });
                """))
        for selector in [".sidebar", "#navigation", "#topbar", "#main"]:
            self.assertTrue(self.wait_for(selector).get_attribute("aria-label"))
        self.wait_for(".local-status").click()
        self.wait_for('.health-body[aria-busy="false"]')
        dialog = self.wait_for(".health-drawer[open]")
        self.assertEqual(dialog.get_attribute("aria-labelledby"), "health-title")
        self.assertTrue(self.wait_for(".health-drawer .icon-button").get_attribute("aria-label"))

    def assert_static_graph(self, selector: str) -> None:
        surface = self.wait_for(selector)
        self.wait_until(lambda driver: surface.get_attribute("data-running") == "false" and
                        int(surface.get_attribute("data-draws") or "0") > 0)
        self.assertTrue(self.driver.execute_async_script("""
            const surface = arguments[0], done = arguments[arguments.length - 1], before = surface.dataset.draws;
            requestAnimationFrame(() => requestAnimationFrame(() => done(before === surface.dataset.draws)));
        """, surface))
        self.assertTrue(self.driver.execute_script("""
            const surface = arguments[0], canvas = surface.tagName === 'CANVAS' ? surface : surface.querySelector('canvas');
            const nodes = canvas.getContext('2d').testNodePositions || [];
            const points = new Set(nodes.map(([x, y]) => `${Math.round(x)},${Math.round(y)}`));
            return points.size > 1 && Math.max(...nodes.map(p => p[0])) - Math.min(...nodes.map(p => p[0])) > 30 &&
              canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data.some(value => value > 0);
        """, surface))

    def test_reduced_motion_graphs_settle_before_first_paint(self) -> None:
        self.driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
        script = self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
            const prototype = CanvasRenderingContext2D.prototype;
            const clear = prototype.clearRect;
            prototype.clearRect = function(...args) { this.testNodePositions = []; return clear.apply(this, args); };
            for (const method of ['arc', 'roundRect']) {
              const original = prototype[method];
              prototype[method] = function(x, y, ...args) {
                (this.testNodePositions ||= []).push(method === 'arc' ? [x, y] : [x + args[0] / 2, y + args[1] / 2]);
                return original.call(this, x, y, ...args);
              };
            }
        """})
        try:
            self.open("#/grafik")
            self.assert_static_graph(".graph-canvas")
            self.open("#/not/" + make_rid("notes/atlas.md"))
            self.assert_static_graph(".mini-graph")
        finally:
            self.driver.execute_cdp_cmd("Page.removeScriptToEvaluateOnNewDocument", {"identifier": script["identifier"]})
            self.driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"features": []})
