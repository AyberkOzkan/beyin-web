from __future__ import annotations

import re
import unittest
from pathlib import Path

from beyin_web.http.server import DRAWING
from scripts.draw_illustrations import DRAWINGS, SIZES, render

IMAGES = Path(__file__).resolve().parents[1] / "beyin_web" / "static" / "img"


class IllustrationTests(unittest.TestCase):
    def test_packaged_drawings_are_exactly_what_the_script_draws(self) -> None:
        files = render()
        self.assertEqual(sorted(path.name for path in IMAGES.iterdir()), sorted(files))
        for name, text in files.items():
            with self.subTest(name=name):
                self.assertEqual((IMAGES / name).read_text(encoding="utf-8"), text)
        self.assertEqual(render(), files)

    def test_thirty_drawings_fill_the_four_slots(self) -> None:
        self.assertEqual({slot: len(recipes) for slot, recipes in DRAWINGS.items()},
                         {"hero-palace": 8, "sidebar-tree": 7, "heading-mountains": 8, "card-window": 7})
        self.assertEqual(len({recipe for recipes in DRAWINGS.values() for recipe in recipes}), 30)
        files = render()
        self.assertEqual(len(set(files.values())), 30)
        for name in files:
            match = DRAWING.fullmatch(name)
            self.assertIsNotNone(match, name)
            assert match is not None
            self.assertIn(match.group(1), SIZES)

    def test_every_drawing_keeps_its_slot_size_and_draws_nothing_outside_it(self) -> None:
        for name, text in render().items():
            with self.subTest(name=name):
                width, height = SIZES[name.rsplit("-", 1)[0]]
                self.assertIn(f'viewBox="0 0 {width} {height}" width="{width}" height="{height}"', text)
                points = [(float(x), float(y)) for x, y in re.findall(r"[ML](-?[0-9.]+) (-?[0-9.]+)", text)]
                self.assertGreater(len(points), 100)
                # A shaky line may wander a few pixels; a recipe with a wrong coordinate goes much further.
                self.assertGreaterEqual(min(x for x, _ in points), -8)
                self.assertLessEqual(max(x for x, _ in points), width + 8)
                self.assertGreaterEqual(min(y for _, y in points), -8)
                self.assertLessEqual(max(y for _, y in points), height + 8)
                self.assertLess(len(text.encode("utf-8")), 20_000)

    def test_drawings_hold_only_paths_and_circles(self) -> None:
        for name, text in render().items():
            with self.subTest(name=name):
                self.assertEqual(set(re.findall(r"<([a-zA-Z]+)", text)), {"svg", "g", "path", "circle"} & set(re.findall(r"<([a-zA-Z]+)", text)))
                self.assertLessEqual(set(re.findall(r"<([a-zA-Z]+)", text)), {"svg", "g", "path", "circle"})
                for forbidden in ("<script", "href", "url(", "style=", "<image", "<foreignObject", "onload"):
                    self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
