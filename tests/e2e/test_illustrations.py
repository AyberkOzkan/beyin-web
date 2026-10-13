from __future__ import annotations

from typing import Any

from tests.e2e.support import PageTestCase


class IllustrationPlacementTests(PageTestCase):
    def picture(self, css: str) -> Any:
        picture = self.wait_for(css)
        self.wait_until(lambda driver: driver.execute_script("return arguments[0].complete && arguments[0].naturalWidth > 0", picture))
        return picture

    def path_of(self, css: str) -> str:
        return str(self.driver.execute_script("return new URL(arguments[0].src).pathname", self.picture(css)))

    def test_each_slot_shows_one_of_its_drawings_at_its_own_size(self) -> None:
        drawings = self.server.drawings
        self.open()
        self.wait_for('.home-page[aria-busy="false"]')
        places = (("#home-greeting .illustration-hero-palace", "hero-palace", 132),
                  ("#home-counts .illustration-card-window", "card-window", 150),
                  ("#sidebar-art .illustration-sidebar-tree", "sidebar-tree", 130))
        for css, slot, height in places:
            with self.subTest(slot=slot):
                self.assertIn(self.path_of(css), drawings[slot])
                self.assertGreaterEqual(round(self.picture(css).rect["height"]), height)
        # The drawings belong to the page: the one beside the greeting is taller than its row, the one in the
        # card lies under the last counter, and the one under the menu reaches the edges of the side bar.
        self.assertTrue(self.driver.execute_script("""
            const box = selector => document.querySelector(selector).getBoundingClientRect();
            const hero = box('#home-greeting .illustration'), row = box('#home-greeting');
            const card = box('#home-counts .illustration'), last = box('#home-counts .home-counter:last-child');
            const tree = box('#sidebar-art'), side = box('.sidebar');
            return hero.height > row.height - 12 && card.left < last.right && card.bottom <= box('#home-counts').bottom + 9 &&
              Math.abs(tree.width - side.width) <= 1;
        """))
        # The drawing under the menu never pushes the vault box out of the window.
        self.assertTrue(self.driver.execute_script(
            "return document.getElementById('vault-status').getBoundingClientRect().bottom <= innerHeight"))
        self.assert_no_overflow()

    def test_heading_drawing_stays_while_browsing_and_leaves_narrow_windows(self) -> None:
        self.open("#/gunlukler/2026-01-12")
        css = ".page-heading .illustration-heading-mountains"
        first = self.path_of(css)
        self.assertIn(first, self.server.drawings["heading-mountains"])
        self.assertGreaterEqual(round(self.picture(css).rect["height"]), 100)
        heading = self.driver.execute_script("return document.querySelector('.page-heading').getBoundingClientRect().height")
        self.assertLess(heading, 110, "the drawing must not make the heading taller")
        sidebar = self.path_of("#sidebar-art img")
        self.driver.execute_script("location.hash = '#/hafiza'")
        self.wait_until(lambda driver: self.text("#main h1") == self.messages["page.memory.title"])
        self.assertIn(self.path_of(css), self.server.drawings["heading-mountains"])
        self.driver.execute_script("location.hash = '#/gunlukler/2026-01-12'")
        self.wait_until(lambda driver: self.text("#main h1") == self.messages["page.journal.title"])
        self.assertEqual(self.path_of(css), first)
        self.assertEqual(self.path_of("#sidebar-art img"), sidebar)
        self.driver.set_window_size(1100, 941)
        self.wait_until(lambda driver: not driver.find_element("css selector", css).is_displayed())
        self.assert_no_overflow((1100,))
        self.driver.set_window_size(1672, 700)
        self.wait_until(lambda driver: not driver.find_element("css selector", "#sidebar-art").is_displayed())

    def test_empty_box_shows_a_drawing_instead_of_the_icon(self) -> None:
        for path in sorted((self.vault / "goals").glob("*.md")) if (self.vault / "goals").is_dir() else []:
            path.unlink()
        self.restart_server()
        self.open("#/hedefler")
        self.wait_for(".state .illustration-card-window")
        boxes = self.all(".state")
        self.assertTrue(boxes)
        for box in boxes:
            self.assertEqual(len(box.find_elements("css selector", ".illustration-card-window")), 1)
            self.assertEqual(box.find_elements("css selector", ".icon"), [])
        self.assertEqual(round(self.picture(".state .illustration-card-window").rect["height"]), 120)
