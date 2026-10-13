from __future__ import annotations

from typing import Any

from tests.e2e.support import PageTestCase

BOXES = """
    const box = node => { const r = node.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
    return {
      doodles: [...document.querySelectorAll('.doodle-layer image')].map(node => ({href: node.getAttribute('href'), box: box(node)})),
      taken: [...document.querySelectorAll('#main .card, #main .illustration, #main .page-heading, #main .state, #topbar')].map(box),
      main: box(document.getElementById('main')),
      styled: document.querySelectorAll('[style]').length,
      hidden: document.querySelector('.doodle-layer').getAttribute('aria-hidden'),
      events: getComputedStyle(document.querySelector('.doodle-layer')).pointerEvents,
    };
"""


class DoodleTests(PageTestCase):
    def state(self) -> dict[str, Any]:
        return dict(self.driver.execute_script(BOXES))

    def settled(self, minimum: int = 1) -> dict[str, Any]:
        self.wait_until(lambda driver: len(self.state()["doodles"]) >= minimum)
        first = self.state()
        self.wait_until(lambda driver: self.state()["doodles"] == first["doodles"] or first.update(self.state()) is not None)
        return self.state()

    def test_doodles_sit_only_on_bare_paper(self) -> None:
        self.open("#/bilgi")
        self.wait_for(".record-reader")
        state = self.settled()
        self.assertEqual((state["hidden"], state["events"], state["styled"]), ("true", "none", 0))
        sources = self.server.drawings["margin-doodle"]
        self.assertEqual(len(sources), 16)
        left, top, right, bottom = state["main"]
        for doodle in state["doodles"]:
            self.assertIn(doodle["href"], sources)
            x1, y1, x2, y2 = doodle["box"]
            self.assertTrue(left <= x1 and x2 <= right and top <= y1 and y2 <= bottom, doodle)
            for taken in state["taken"]:
                # A turned picture reports a slightly larger box; a few pixels of it may brush an edge.
                apart = x2 - 6 <= taken[0] or taken[2] <= x1 + 6 or y2 - 6 <= taken[1] or taken[3] <= y1 + 6
                self.assertTrue(apart, (doodle, taken))
        self.assertEqual(len({doodle["href"] for doodle in state["doodles"]}), len(state["doodles"]))
        # The reader still takes clicks through the layer.
        self.wait_for(".knowledge-columns a.list-row, .knowledge-columns .list-row").click()
        self.assertEqual(self.console_errors(), [])

    def test_a_full_page_has_none_and_the_places_do_not_jump(self) -> None:
        self.open()
        self.wait_for('.home-page[aria-busy="false"]')
        self.wait_until(lambda driver: driver.execute_script("return document.readyState") == "complete")
        self.assertEqual(self.state()["doodles"], [])
        self.driver.execute_script("location.hash = '#/bilgi'")
        self.wait_for(".record-reader")
        before = self.settled()["doodles"]
        self.driver.set_window_size(1500, 941)
        self.wait_until(lambda driver: driver.execute_script("return innerWidth < 1600"))
        self.driver.set_window_size(1672, 941)
        self.wait_until(lambda driver: self.state()["doodles"] == before)
        self.assert_no_overflow()
