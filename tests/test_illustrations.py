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

    def test_every_drawing_is_its_own_and_every_slot_has_a_choice(self) -> None:
        self.assertEqual({slot: len(recipes) for slot, recipes in DRAWINGS.items()},
                         {"hero-palace": 8, "sidebar-tree": 7, "heading-mountains": 8, "card-window": 8, "margin-doodle": 16})
        self.assertEqual(len({recipe for recipes in DRAWINGS.values() for recipe in recipes}), 47)
        files = render()
        self.assertEqual(len(set(files.values())), 47)
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
                self.assertGreater(len(points), 30 if name.startswith("margin-doodle") else 100)
                # A shaky line may wander a few pixels; a recipe with a wrong coordinate goes much further.
                self.assertGreaterEqual(min(x for x, _ in points), -8)
                self.assertLessEqual(max(x for x, _ in points), width + 8)
                self.assertGreaterEqual(min(y for _, y in points), -8)
                self.assertLessEqual(max(y for _, y in points), height + 8)
                self.assertLess(len(text.encode("utf-8")), 48_000)

    def test_drawings_hold_only_strokes_circles_and_their_own_grain_filter(self) -> None:
        allowed = {"svg", "g", "path", "circle", "defs", "filter", "feTurbulence", "feDisplacementMap", "feColorMatrix", "feComposite"}
        for name, text in render().items():
            with self.subTest(name=name):
                self.assertLessEqual(set(re.findall(r"<([a-zA-Z]+)", text)), allowed)
                # The only reference is to the filter inside the same file; nothing is loaded from anywhere.
                self.assertEqual(re.findall(r"url\([^)]*\)", text), ["url(#pencil)"])
                self.assertEqual(text.count('<filter id="pencil"'), 1)
                for forbidden in ("<script", "href", "style=", "<image", "<foreignObject", "onload", "feImage"):
                    self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
