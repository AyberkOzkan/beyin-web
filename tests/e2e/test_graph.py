from __future__ import annotations

from typing import Any
from statistics import median
from unittest.mock import patch
from urllib.parse import parse_qs

from beyin_web.vault.records import make_rid
from tests.e2e.support import PageTestCase


class GraphTests(PageTestCase):
    beyin = False

    def canvas(self) -> Any:
        return self.wait_for(".graph-canvas")

    def counts(self) -> tuple[int, int]:
        canvas = self.canvas()
        return int(canvas.get_attribute("data-nodes")), int(canvas.get_attribute("data-edges"))

    def choose(self, css: str, value: str) -> None:
        from selenium.webdriver.support.ui import Select
        previous = self.driver.find_element("css selector", ".graph-page")
        from selenium.webdriver.support import expected_conditions as conditions
        Select(self.wait_for(css)).select_by_value(value)
        # A detached element cannot be passed to a script; ask the driver whether it went stale.
        self.wait_until(conditions.staleness_of(previous))
        self.wait_until(lambda driver: not self.all(".graph-area .skeleton"))

    def select_note(self, rid: str) -> None:
        from selenium.webdriver.common.keys import Keys
        self.canvas()
        item = self.driver.find_element("css selector", f'.graph-node-list button[data-rid="{rid}"]')
        self.driver.execute_script("arguments[0].focus()", item)
        item.send_keys(Keys.ENTER)
        self.wait_for(f'.graph-selection[data-rid="{rid}"]')

    def query(self) -> dict[str, list[str]]:
        return parse_qs(self.hash().partition("?")[2])

    def snapshot(self) -> dict[str, Any]:
        return self.driver.execute_script("""
            let result;
            document.querySelector('.graph-canvas').dispatchEvent(new CustomEvent('graph:inspect', {
              detail: { respond: value => { result = value; } }
            }));
            return result;
        """)

    def assert_frame_activity(self, canvas: Any, running: bool) -> None:
        changed = self.driver.execute_async_script("""
            const canvas = arguments[0], done = arguments[arguments.length - 1], before = canvas.dataset.draws;
            requestAnimationFrame(() => requestAnimationFrame(() => done(before !== canvas.dataset.draws)));
        """, canvas)
        self.assertEqual(changed, running)

    def assert_layout(self) -> dict[str, Any]:
        self.wait_until(lambda driver: self.canvas().get_attribute("data-settled") == "true", timeout=3)
        result = self.snapshot()
        self.assertGreaterEqual(result["metrics"]["minimumDistance"], 36)
        self.assertGreaterEqual(result["metrics"]["medianLinkDistance"], 120)
        for spread in result["metrics"]["leafSpreads"]:
            if spread["leaves"] >= 60:
                self.assertGreaterEqual(spread["ratio"], 1.5)
        self.assertTrue(all(node["screen"] is not None for node in result["nodes"]))
        self.assertTrue(self.driver.execute_script("""
            const canvas = document.querySelector('.graph-canvas'), bounds = canvas.getBoundingClientRect();
            return arguments[0].every(node => node.screen.x >= node.screen.radius &&
              node.screen.x <= bounds.width - node.screen.radius && node.screen.y >= node.screen.radius &&
              node.screen.y <= bounds.height - node.screen.radius);
        """, result["nodes"]))
        return result

    def test_canvas_counts_painted_pixels_privacy_and_layout(self) -> None:
        golden = self.golden("graph")
        self.open("#/grafik")
        self.assertEqual(self.counts(), (len(golden["nodes"]), len(golden["edges"])))
        self.wait_until(lambda driver: int(self.canvas().get_attribute("data-draws")) > 0)
        painted = self.driver.execute_script("""
            const canvas = document.querySelector('.graph-canvas');
            const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
            for (let index = 3; index < pixels.length; index += 4) if (pixels[index]) return true;
            return false;
        """)
        self.assertTrue(painted)
        scene = self.driver.execute_script("""
            const canvas = document.querySelector('.graph-canvas');
            const pixel = [...canvas.getContext('2d').getImageData(1, 1, 1, 1).data];
            const styles = getComputedStyle(canvas);
            const hex = styles.getPropertyValue('--space').trim().slice(1);
            const expected = [0, 2, 4].map(index => parseInt(hex.slice(index, index + 2), 16));
            const paper = styles.getPropertyValue('--paper').trim().slice(1);
            const paperRgb = [0, 2, 4].map(index => parseInt(paper.slice(index, index + 2), 16));
            return { pixel, expected, paper: `rgb(${paperRgb.join(', ')})`,
              body: getComputedStyle(document.body).backgroundColor,
              area: getComputedStyle(document.querySelector('.graph-area')).backgroundColor };
        """)
        self.assertEqual(scene["pixel"], scene["expected"] + [255])
        self.assertEqual(scene["body"], scene["paper"])
        self.assertEqual(scene["area"], "rgb(" + ", ".join(map(str, scene["expected"])) + ")")
        self.assertTrue(self.driver.execute_script("""
            const canvas = document.querySelector('.graph-canvas'), bounds = canvas.getBoundingClientRect();
            return canvas.width === Math.round(bounds.width * devicePixelRatio) &&
              canvas.height === Math.round(bounds.height * devicePixelRatio);
        """))
        titles = self.driver.execute_script("return document.querySelector('.graph-node-list').textContent")
        self.assertNotIn("GIZLI-SIZINTI-ISARETI", titles)
        self.assertEqual(self.all(f'.graph-node-list [data-rid="{make_rid("notes/gizli.md")}"]'), [])
        self.assertEqual(len(self.all(".graph-node-list button")), len(golden["nodes"]))
        self.assert_no_overflow()
        self.assert_clean_text()
        self.driver.execute_script("document.dispatchEvent(new CustomEvent('beyin:changed'))")
        self.assertEqual(self.counts(), (len(golden["nodes"]), len(golden["edges"])))

    def test_accessible_selection_panel_neighbors_and_note_link(self) -> None:
        rid = make_rid("notes/atlas.md")
        self.open("#/grafik")
        self.select_note(rid)
        self.assertEqual(self.text(".graph-selected-title"), "Atlas")
        self.assertEqual(self.text('.graph-fields [data-field="type"]'), self.messages["graph.kind.note"])
        self.assertEqual(self.text('.graph-fields [data-field="project"]'), "atlas")
        self.assertEqual(self.text('.graph-fields [data-field="connections"]'), "4")
        self.assertEqual({item.text for item in self.all(".graph-neighbors button")},
                         {"Kavram bir", "Kavram iki", "Atlas A2: İkinci aşamayı tamamla"})
        self.wait_for(".graph-summary p")
        self.assertEqual(self.text(".graph-summary"), self.golden("record")["excerpt"])
        self.wait_for(".graph-open-note").click()
        self.wait_until(lambda driver: self.hash() == "#/not/" + rid)
        self.wait_for(f'.record-reader[data-rid="{rid}"]')
        self.assert_clean_text()

    def test_filters_counts_url_refresh_and_history(self) -> None:
        self.open("#/grafik")
        self.canvas()
        self.wait_until(lambda driver: len(self.all('#graph-project option[value="atlas"]')) == 1)
        self.choose("#graph-project", "atlas")
        self.wait_until(lambda driver: self.counts()[0] == 3)
        self.assertEqual(self.query()["proje"], ["atlas"])
        self.choose("#graph-kind", "fact")
        self.wait_for(".graph-area .state")
        self.assertEqual(len(self.all(".graph-node-list button")), 0)
        self.assertEqual(self.query()["tur"], ["fact"])
        self.wait_for("#graph-connected").click()
        self.wait_until(lambda driver: self.counts()[0] == 1)
        self.assertEqual(self.query()["yalniz"], ["0"])
        self.choose("#graph-project", "")
        self.wait_until(lambda driver: self.counts()[0] == 2)
        self.choose("#graph-kind", "")
        self.wait_until(lambda driver: self.counts()[0] > len(self.golden("graph")["nodes"]))
        isolated = make_rid("notes/serbest.md")
        self.assertEqual(len(self.all(f'.graph-node-list [data-rid="{isolated}"]')), 1)
        before = self.counts()
        self.wait_for("#graph-receipts").click()
        self.wait_until(lambda driver: self.counts()[0] > before[0] and self.counts()[1] > before[1])
        self.assertEqual(self.query()["receipt"], ["1"])
        self.choose("#graph-kind", "note")
        self.choose("#graph-project", "atlas")
        self.wait_until(lambda driver: self.counts()[0] == 1)
        self.assertEqual(self.query(), {"tur": ["note"], "proje": ["atlas"], "receipt": ["1"], "yalniz": ["0"]})
        self.driver.refresh()
        self.wait_until(lambda driver: self.counts()[0] == 1)
        self.assertEqual(self.wait_for("#graph-kind").get_attribute("value"), "note")
        self.assertEqual(self.wait_for("#graph-project").get_attribute("value"), "atlas")
        self.assertTrue(self.wait_for("#graph-receipts").is_selected())
        self.assertFalse(self.wait_for("#graph-connected").is_selected())
        self.wait_for("#graph-connected").click()
        self.wait_for(".graph-area .state")
        self.driver.back()
        self.wait_until(lambda driver: self.counts()[0] == 1)
        self.assertFalse(self.wait_for("#graph-connected").is_selected())
        self.assert_clean_text()

    def test_focus_return_and_keyboard_focus_action(self) -> None:
        from selenium.webdriver.common.keys import Keys
        rid = make_rid("notes/atlas.md")
        self.open("#/grafik?odak=" + rid)
        self.wait_for(f'.graph-selection[data-rid="{rid}"]')
        self.assertEqual(self.canvas().get_attribute("data-selected"), rid)
        self.wait_for(".graph-back").click()
        self.wait_until(lambda driver: self.hash() == "#/grafik")
        self.canvas()
        item = self.driver.find_element("css selector", f'.graph-node-list button[data-rid="{rid}"]')
        self.driver.execute_script("arguments[0].focus()", item)
        item.send_keys(Keys.SHIFT, Keys.ENTER)
        self.wait_until(lambda driver: self.query().get("odak") == [rid])
        self.wait_for(f'.graph-selection[data-rid="{rid}"]')

    def test_search_highlights_and_centers_enter_without_reloading(self) -> None:
        from selenium.webdriver.common.keys import Keys
        self.open("#/grafik")
        self.canvas()
        field = self.wait_for(".graph-search input")
        field.send_keys("KAVRAM")
        self.wait_until(lambda driver: self.canvas().get_attribute("data-matches") == "2")
        self.assertEqual(self.query()["q"], ["KAVRAM"])
        field.send_keys(Keys.ENTER)
        self.wait_for(".graph-selected-title")
        self.assertIn(self.text(".graph-selected-title"), {"Kavram bir", "Kavram iki"})
        self.driver.refresh()
        self.wait_until(lambda driver: self.canvas().get_attribute("data-matches") == "2")
        self.assertEqual(self.wait_for(".graph-search input").get_attribute("value"), "KAVRAM")
        self.assert_clean_text()

    def test_receipt_focus_keeps_reference_neighbors(self) -> None:
        receipt = self.golden("record")["receipts"][0]
        self.open("#/grafik?receipt=1&odak=" + receipt["rid"])
        self.wait_for(f'.graph-selection[data-rid="{receipt["rid"]}"]')
        self.assertGreater(self.counts()[0], 1)
        self.assertGreater(self.counts()[1], 0)
        expected = {note["title"] for note in receipt["refs"]}
        self.assertTrue(expected.issubset({item.text for item in self.all(".graph-neighbors button")}))
        self.assert_clean_text()

    def test_drift_after_settling_selection_escape_visibility_and_destroy(self) -> None:
        from selenium.webdriver.common.keys import Keys
        self.open("#/grafik")
        self.canvas()
        self.assert_layout()
        self.wait_until(lambda driver: self.canvas().get_attribute("data-drifting") == "true")
        self.assert_frame_activity(self.canvas(), True)
        before = self.snapshot()
        self.assert_frame_activity(self.canvas(), True)
        after = self.snapshot()
        self.assertEqual([(node["x"], node["y"]) for node in before["nodes"]],
                         [(node["x"], node["y"]) for node in after["nodes"]])
        self.assertNotEqual([node["screen"] for node in before["nodes"]], [node["screen"] for node in after["nodes"]])
        self.select_note(make_rid("notes/atlas.md"))
        self.assertEqual(self.canvas().get_attribute("data-drifting"), "false")
        self.assertEqual(self.canvas().get_attribute("data-running"), "false")
        self.assert_frame_activity(self.canvas(), False)
        self.driver.switch_to.active_element.send_keys(Keys.ESCAPE)
        self.wait_until(lambda driver: self.canvas().get_attribute("data-drifting") == "true")
        self.assertEqual(self.canvas().get_attribute("data-selected"), "")
        self.assertEqual(self.all(".graph-selection"), [])
        self.assert_frame_activity(self.canvas(), True)
        self.driver.execute_script("window.__oldGraphCanvas = document.querySelector('.graph-canvas')")
        previous_zoom = float(self.canvas().get_attribute("data-zoom"))
        self.wait_for('.graph-zoom button[aria-label="' + self.messages["graph.zoomIn"] + '"]').click()
        self.wait_until(lambda driver: float(self.canvas().get_attribute("data-zoom")) > previous_zoom)
        self.driver.execute_script("""
            Object.defineProperty(document, 'hidden', {configurable: true, value: true});
            document.dispatchEvent(new Event('visibilitychange'));
        """)
        self.assertEqual(self.canvas().get_attribute("data-running"), "false")
        self.assertEqual(self.canvas().get_attribute("data-drifting"), "false")
        self.assert_frame_activity(self.canvas(), False)
        self.driver.execute_script("""
            Object.defineProperty(document, 'hidden', {configurable: true, value: false});
            document.dispatchEvent(new Event('visibilitychange'));
        """)
        self.wait_until(lambda driver: self.canvas().get_attribute("data-drifting") == "true")
        self.assert_frame_activity(self.canvas(), True)
        self.driver.execute_script("location.hash = '/bilgi'")
        self.wait_until(lambda driver: driver.execute_script("return __oldGraphCanvas.dataset.destroyed === 'true'"))
        self.assertEqual(self.driver.execute_script("return __oldGraphCanvas.dataset.running"), "false")
        self.assertEqual(self.driver.execute_script("return __oldGraphCanvas.dataset.drifting"), "false")
        unchanged = self.driver.execute_async_script("""
            const done = arguments[arguments.length - 1], before = __oldGraphCanvas.dataset.draws;
            requestAnimationFrame(() => requestAnimationFrame(() => done(before === __oldGraphCanvas.dataset.draws)));
        """)
        self.assertTrue(unchanged)

    def test_graph_error_retry_and_empty_graph(self) -> None:
        original = self.server.api._build

        def fail(*args: Any, **kwargs: Any) -> Any:
            if args[0] == "graph" and args[1].get("kinds") != "memory":
                raise RuntimeError("synthetic_failure")
            return original(*args, **kwargs)

        with patch.object(self.server.api, "_build", side_effect=fail):
            self.open("#/grafik")
            retry = self.wait_for(".graph-area [role='alert'] button")
            self.assertEqual(retry.text, self.messages["action.retry"])
            errors = self.console_errors()
            self.assertTrue(errors)
            self.assertTrue(all("500" in entry["message"] and "/api/v1/graph" in entry["message"] for entry in errors), errors)
        retry.click()
        self.canvas()
        self.open("#/grafik?tur=task")
        self.wait_for(".graph-area .state")
        self.assertIn(self.messages["graph.emptyMessage"], self.text(".graph-area"))
        self.assert_clean_text()

    def test_pause_control_name_pressed_state_and_selection_independence(self) -> None:
        from selenium.webdriver.common.keys import Keys
        self.open("#/grafik")
        self.wait_until(lambda driver: self.canvas().get_attribute("data-drifting") == "true")
        control = self.wait_for(".graph-motion")
        original_hash = self.hash()
        self.assertEqual(control.get_attribute("aria-pressed"), "false")
        self.assertEqual(control.get_attribute("aria-label"), self.messages["graph.stopMotion"])
        control.click()
        self.assertEqual(control.get_attribute("aria-pressed"), "true")
        self.assertEqual(control.get_attribute("aria-label"), self.messages["graph.startMotion"])
        self.assertEqual(self.canvas().get_attribute("data-drifting"), "false")
        self.assertEqual(self.canvas().get_attribute("data-running"), "false")
        self.assert_frame_activity(self.canvas(), False)
        self.select_note(make_rid("notes/atlas.md"))
        self.driver.switch_to.active_element.send_keys(Keys.ESCAPE)
        self.assertEqual(self.canvas().get_attribute("data-running"), "false")
        self.assert_frame_activity(self.canvas(), False)
        control.click()
        self.wait_until(lambda driver: self.canvas().get_attribute("data-drifting") == "true")
        self.assertEqual(control.get_attribute("aria-pressed"), "false")
        self.assertEqual(control.get_attribute("aria-label"), self.messages["graph.stopMotion"])
        self.assert_frame_activity(self.canvas(), True)
        self.assertEqual(self.hash(), original_hash)

    def test_empty_click_clears_selection_but_panning_keeps_it(self) -> None:
        from selenium.webdriver.common.action_chains import ActionChains
        self.open("#/grafik")
        rid = make_rid("notes/atlas.md")
        self.select_note(rid)
        self.wait_for("#main h1").click()
        canvas = self.canvas()
        canvas.location_once_scrolled_into_view
        bounds = canvas.rect
        x = 12 - bounds["width"] / 2
        y = 12 - bounds["height"] / 2
        ActionChains(self.driver).move_to_element_with_offset(canvas, x, y).click_and_hold().move_by_offset(20, 10).release().perform()
        self.assertEqual(canvas.get_attribute("data-selected"), rid)
        self.assertEqual(canvas.get_attribute("data-drifting"), "false")
        ActionChains(self.driver).move_to_element_with_offset(canvas, x, y).click().perform()
        self.wait_until(lambda driver: canvas.get_attribute("data-drifting") == "true")
        self.assertEqual(canvas.get_attribute("data-selected"), "")
        self.assertEqual(self.all(".graph-selection"), [])

    def test_hover_dims_non_neighbors_and_restores_labels_at_low_zoom(self) -> None:
        from selenium.webdriver.common.action_chains import ActionChains
        self.open("#/grafik")
        self.assert_layout()
        self.wait_for(".graph-motion").click()
        canvas = self.canvas()
        self.driver.execute_script("""
            const canvas = arguments[0], bounds = canvas.getBoundingClientRect();
            const k = Number(canvas.dataset.zoom);
            canvas.dispatchEvent(new WheelEvent('wheel', {deltaY: Math.log(k / 0.45) / 0.001,
              cancelable: true, clientX: bounds.left + bounds.width / 2, clientY: bounds.top + bounds.height / 2}));
        """, canvas)
        self.wait_until(lambda driver: float(canvas.get_attribute("data-zoom")) < 0.6)
        snapshot = self.snapshot()
        neighbors: dict[str, set[str]] = {node["id"]: set() for node in snapshot["nodes"]}
        for edge in snapshot["edges"]:
            neighbors[edge["source"]].add(edge["target"])
            neighbors[edge["target"]].add(edge["source"])
        target, other = next((node, other) for node in snapshot["nodes"] for other in snapshot["nodes"]
                             if node["id"] != other["id"] and other["id"] not in neighbors[node["id"]])
        sample = """
            const canvas = arguments[0], target = arguments[1], other = arguments[2], ctx = canvas.getContext('2d');
            const ratio = canvas.width / canvas.getBoundingClientRect().width;
            const x = Math.round(other.x * ratio), y = Math.round(other.y * ratio);
            const pixel = [...ctx.getImageData(x, y, 1, 1).data].slice(0, 3);
            const hex = getComputedStyle(canvas).getPropertyValue('--space-ink').trim().slice(1);
            const ink = [0, 2, 4].map(index => parseInt(hex.slice(index, index + 2), 16));
            const left = Math.max(0, Math.floor((target.x - 85) * ratio));
            const top = Math.max(0, Math.floor((target.y + target.radius + 8) * ratio));
            const width = Math.min(canvas.width - left, Math.ceil(170 * ratio));
            const height = Math.min(canvas.height - top, Math.ceil(23 * ratio));
            const pixels = ctx.getImageData(left, top, width, height).data;
            let inkPixels = 0;
            for (let i = 0; i < pixels.length; i += 4) {
              if (ink.every((value, channel) => Math.abs(value - pixels[i + channel]) < 35)) inkPixels++;
            }
            return { brightness: pixel.reduce((sum, value) => sum + value, 0), inkPixels };
        """
        before = self.driver.execute_script(sample, canvas, target["screen"], other["screen"])
        self.assertEqual(before["inkPixels"], 0)
        canvas.location_once_scrolled_into_view
        bounds = canvas.rect
        ActionChains(self.driver).move_to_element_with_offset(canvas, target["screen"]["x"] - bounds["width"] / 2,
                                                            target["screen"]["y"] - bounds["height"] / 2).perform()
        self.wait_until(lambda driver: canvas.get_attribute("data-hovered") == target["id"])
        after = self.driver.execute_script(sample, canvas, target["screen"], other["screen"])
        self.assertLess(after["brightness"], before["brightness"])
        self.assertGreater(after["inkPixels"], 5)
        self.wait_for("#main h1").click()
        self.wait_until(lambda driver: canvas.get_attribute("data-hovered") == "")
        restored = self.driver.execute_script(sample, canvas, target["screen"], other["screen"])
        self.assertEqual(restored, before)
        self.assert_clean_text()

    def test_sixty_leaf_star_spreads_over_multiple_orbits(self) -> None:
        original = self.server.api._build
        nodes = [{"id": "hub", "title": "Hub", "kind": "note", "degree": 60, "project": None}]
        nodes.extend({"id": str(index), "title": f"Leaf {index}", "kind": "note", "degree": 1, "project": None}
                     for index in range(60))
        edges = [{"source": "hub", "target": str(index), "type": "link"} for index in range(60)]

        def star(*args: Any, **kwargs: Any) -> Any:
            if args[0] == "graph" and args[1].get("kinds") != "memory":
                return {"nodes": nodes, "edges": edges}
            return original(*args, **kwargs)

        with patch.object(self.server.api, "_build", side_effect=star):
            self.open("#/grafik")
            result = self.assert_layout()
            spread = next(spread for spread in result["metrics"]["leafSpreads"] if spread["id"] == "hub")
            self.assertEqual(spread["leaves"], 60)
            self.assertGreaterEqual(spread["ratio"], 1.5)

    def test_five_hundred_node_layout_budget_and_sixty_drift_frame_median(self) -> None:
        from scripts.synthetic_vault import generate_vault
        self.vault = self.vault.parent / "synthetic-500"
        generate_vault(self.vault, notes=500)
        self.restart_server()
        script = self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
            const prototype = CanvasRenderingContext2D.prototype, clear = prototype.clearRect;
            prototype.clearRect = function(...args) {
              if (this.canvas.matches('.graph-canvas') && this.testLayoutStarted === undefined) {
                this.testLayoutStarted = performance.now();
                const observer = new MutationObserver(() => {
                  if (this.canvas.dataset.settled === 'true') {
                    this.testLayoutMilliseconds = performance.now() - this.testLayoutStarted;
                    observer.disconnect();
                  }
                });
                observer.observe(this.canvas, {attributes: true, attributeFilter: ['data-settled']});
              }
              return clear.apply(this, args);
            };
        """})
        try:
            self.open("#/grafik")
            self.assertEqual(self.counts(), (500, 1697))
            self.assert_layout()
            elapsed = self.driver.execute_script("return document.querySelector('.graph-canvas').getContext('2d').testLayoutMilliseconds")
            self.assertIsNotNone(elapsed)
            self.assertLessEqual(elapsed, 3000)
            self.wait_until(lambda driver: self.canvas().get_attribute("data-drifting") == "true")
            samples = self.driver.execute_async_script("""
                const canvas = arguments[0], done = arguments[arguments.length - 1], ctx = canvas.getContext('2d');
                const clear = ctx.clearRect, reset = ctx.resetTransform, samples = [];
                let started;
                ctx.clearRect = function(...args) { started = performance.now(); return clear.apply(this, args); };
                ctx.resetTransform = function(...args) {
                  const result = reset.apply(this, args);
                  samples.push(performance.now() - started);
                  if (samples.length === 60) { ctx.clearRect = clear; ctx.resetTransform = reset; done(samples); }
                  return result;
                };
            """, self.canvas())
            self.assertEqual(len(samples), 60)
            frame_median = median(samples)
            print(f"Graph 500: layout {elapsed:.2f} ms; drift median {frame_median:.2f} ms (60 frames)", flush=True)
            self.assertLessEqual(frame_median, 16)
            self.assert_no_overflow()
            self.assert_clean_text()
        finally:
            self.driver.execute_cdp_cmd("Page.removeScriptToEvaluateOnNewDocument", {"identifier": script["identifier"]})

    def test_project_filter_and_summary_errors_retry(self) -> None:
        atlas = make_rid("notes/atlas.md")
        for path, selector, loaded in [
            ("projects", ".graph-project-state [role='alert'] button", '#graph-project option[value="atlas"]'),
            ("records/" + atlas, ".graph-summary [role='alert'] button", ".graph-summary p"),
        ]:
            with self.subTest(path=path):
                self.restart_server()
                original = self.server.api._build

                def fail(*args: Any, **kwargs: Any) -> Any:
                    if args[0] == path:
                        raise RuntimeError("synthetic_failure")
                    return original(*args, **kwargs)

                with patch.object(self.server.api, "_build", side_effect=fail):
                    self.open("#/grafik")
                    if path.startswith("records/"):
                        self.select_note(atlas)
                    retry = self.wait_for(selector)
                    errors = self.console_errors()
                    self.assertTrue(errors)
                    self.assertTrue(all("500" in entry["message"] and "/api/v1/" + path in entry["message"] for entry in errors), errors)
                retry.click()
                self.wait_until(lambda driver: len(self.all(loaded)) > 0)

    def test_canvas_pointer_hover_drag_wheel_and_double_click(self) -> None:
        from selenium.webdriver.common.action_chains import ActionChains
        atlas = make_rid("notes/atlas.md")
        self.open("#/grafik?odak=" + atlas)
        self.wait_until(lambda driver: self.canvas().get_attribute("data-running") == "false")
        canvas = self.canvas()
        canvas.location_once_scrolled_into_view
        ActionChains(self.driver).move_to_element(canvas).perform()
        self.wait_until(lambda driver: self.canvas().get_attribute("data-hovered") == atlas)
        before = int(canvas.get_attribute("data-draws"))
        ActionChains(self.driver).click_and_hold().move_by_offset(45, 20).release().perform()
        self.wait_until(lambda driver: int(self.canvas().get_attribute("data-draws")) > before)
        self.wait_until(lambda driver: self.canvas().get_attribute("data-running") == "false")
        previous_zoom = float(self.canvas().get_attribute("data-zoom"))
        self.driver.execute_script("""
            const canvas = arguments[0], bounds = canvas.getBoundingClientRect();
            canvas.dispatchEvent(new WheelEvent('wheel', {deltaY: -150, cancelable: true,
              clientX: bounds.left + bounds.width / 2, clientY: bounds.top + bounds.height / 2}));
        """, canvas)
        self.wait_until(lambda driver: float(self.canvas().get_attribute("data-zoom")) > previous_zoom)
        self.wait_until(lambda driver: self.canvas().get_attribute("data-running") == "false")
        self.wait_for(".graph-back").click()
        self.wait_until(lambda driver: self.hash() == "#/grafik")
        self.canvas()
        self.select_note(atlas)
        self.wait_for(".graph-search input").send_keys("Atlas")
        from selenium.webdriver.common.keys import Keys
        self.wait_for(".graph-search input").send_keys(Keys.ENTER)
        self.wait_until(lambda driver: self.canvas().get_attribute("data-running") == "false")
        ActionChains(self.driver).move_to_element(self.canvas()).double_click().perform()
        self.wait_until(lambda driver: "odak" in self.query())

    def test_large_graph_uses_two_hop_focus(self) -> None:
        original = self.server.api._build
        atlas = make_rid("notes/atlas.md")
        requests: list[dict[str, str]] = []

        def large(*args: Any, **kwargs: Any) -> Any:
            if args[0] != "graph" or args[1].get("kinds") == "memory":
                return original(*args, **kwargs)
            requests.append(dict(args[1]))
            nodes = [{"id": atlas, "title": "Atlas", "kind": "note", "project": "atlas", "degree": 2}]
            nodes.extend({"id": f"{index:012x}", "title": f"Synthetic {index}", "kind": "note", "project": None, "degree": 2}
                         for index in range(1501))
            edges = [{"source": node["id"], "target": nodes[(index + 1) % len(nodes)]["id"], "type": "link"}
                     for index, node in enumerate(nodes)]
            if args[1].get("focus"):
                nearby = {atlas, nodes[1]["id"], nodes[2]["id"], nodes[-1]["id"], nodes[-2]["id"]}
                nodes = [node for node in nodes if node["id"] in nearby]
                edges = [edge for edge in edges if edge["source"] in nearby and edge["target"] in nearby]
            return {"nodes": nodes, "edges": edges}

        with patch.object(self.server.api, "_build", side_effect=large):
            self.open("#/grafik")
            self.wait_for(".graph-notice")
            self.assertEqual(self.counts()[0], 5)
            self.assertEqual(self.query()["odak"], [atlas])
            self.assertTrue(any(request.get("focus") == atlas and request.get("depth") == "2" for request in requests))
            self.wait_for(f'.graph-selection[data-rid="{atlas}"]')
            self.assert_no_overflow()
            self.assert_clean_text()
