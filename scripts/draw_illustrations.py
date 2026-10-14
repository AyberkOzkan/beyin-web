"""Draw the pencil-style illustrations of the interface.

    py -3 scripts/draw_illustrations.py [--out beyin_web/static/img]

The drawings of the four slots; a page shows one of its slot's drawings at random. They are meant to read as
pencil on paper: every line is drawn more than once with a changing pressure, a long line has a faint first
attempt under it, quick strokes run past their ends, shaded sides are hatched and rubbed, and a grain filter
breaks the strokes the way paper breaks graphite. The numbers are seeded: a run always writes the same files,
and a drawing changes only when its recipe below does.
"""
from __future__ import annotations

import argparse
import math
import random
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPHITE = "#333331"
GLOW = "#EFE6D0"
SIZES = {"hero-palace": (520, 170), "sidebar-tree": (216, 180), "heading-mountains": (720, 96), "card-window": (200, 140),
         "margin-doodle": (120, 120), "app-icon": (256, 256)}
PAPER = "#F4EEE2"
Point = tuple[float, float]


class Sketch:
    def __init__(self, slot: str, seed: int) -> None:
        self.width, self.height = SIZES[slot]
        # A doodle is drawn lightly: it must stay behind the page, not compete with it.
        self.pressure = 0.72 if slot == "margin-doodle" else 1.0
        self.random = random.Random(seed)
        self.grain = seed
        self.strokes: dict[tuple[float, float], list[str]] = {}
        self.fills: list[str] = []

    # --- strokes ---------------------------------------------------------------------------------------------

    def _stroke(self, points: list[Point], weight: float, opacity: float, shake: float) -> None:
        path = []
        for index, (x, y) in enumerate(points):
            x += self.random.uniform(-shake, shake)
            y += self.random.uniform(-shake, shake)
            path.append(f"{'M' if index == 0 else 'L'}{x:.1f} {y:.1f}")
        # The drawings are shown at about half their size; a firm line needs some body to survive that.
        self.strokes.setdefault((round(weight * (1.25 if weight < 1.9 else 1.0), 2), round(opacity, 2)), []).append("".join(path))

    def line(self, points: list[Point], *, weight: float = 1.1, opacity: float = 0.85, shake: float = 0.9,
             passes: int = 2) -> None:
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))
        if passes > 1 and length > 14:
            # A quick stroke starts before its mark and runs a little past it.
            (x1, y1), (x2, y2) = points[0], points[1]
            (x3, y3), (x4, y4) = points[-2], points[-1]
            head, tail = self.random.uniform(0.6, 2.4), self.random.uniform(0.6, 2.4)
            first, last = math.hypot(x2 - x1, y2 - y1) or 1, math.hypot(x4 - x3, y4 - y3) or 1
            points = [(x1 - (x2 - x1) / first * head, y1 - (y2 - y1) / first * head), *points[1:-1],
                      (x4 + (x4 - x3) / last * tail, y4 + (y4 - y3) / last * tail)]
        if passes > 1 and weight >= 1.0 and length > 34:
            # The first, light attempt at a long line stays visible under the firm one.
            self._stroke(points, 0.5, 0.3, shake * 2.4)
        for _ in range(passes):
            pressure = self.random.choice((0.75, 0.9, 1.0, 1.1, 1.25))
            self._stroke(points, weight * pressure, (opacity / passes + 0.25) * min(1.0, 0.75 + pressure * 0.25), shake)

    def rub(self, points: list[Point], width: float, opacity: float = 0.09) -> None:
        """Graphite laid with the side of the pencil: many close, pale strokes with ragged ends, not one band."""
        (x1, y1), (x2, y2) = points[0], points[-1]
        length = math.hypot(x2 - x1, y2 - y1) or 1
        across = (-(y2 - y1) / length, (x2 - x1) / length)
        count = max(3, int(width / 1.5))
        for index in range(count):
            shift = (index / (count - 1) - 0.5) * width
            start, end = self.random.uniform(0, 0.22), self.random.uniform(0.78, 1)
            self._stroke([(x1 + (x2 - x1) * start + across[0] * shift, y1 + (y2 - y1) * start + across[1] * shift),
                          (x1 + (x2 - x1) * end + across[0] * shift, y1 + (y2 - y1) * end + across[1] * shift)],
                         2.0, opacity * 1.5, 0.7)

    def shadow(self, x: float, y: float, width: float) -> None:
        for _ in range(max(3, int(width / 5))):
            start = x - width / 2 + self.random.uniform(0, width * 0.5)
            self._stroke([(start, y + self.random.uniform(0, 3)), (start + self.random.uniform(width * 0.25, width * 0.6), y + self.random.uniform(0, 3))],
                         0.6, 0.3, 0.4)

    def curve(self, start: Point, end: Point, bend: float, **style: float) -> None:
        (x1, y1), (x2, y2) = start, end
        steps = max(6, int(math.hypot(x2 - x1, y2 - y1) / 9))
        self.line([(x1 + (x2 - x1) * step / steps, y1 + (y2 - y1) * step / steps - math.sin(step / steps * math.pi) * bend)
                   for step in range(steps + 1)], **style)

    def sample(self, points: list[Point], steps: int = 6) -> list[Point]:
        """Points along a smooth curve through the given ones (Catmull-Rom)."""
        padded = [points[0], *points, points[-1]]
        curve: list[Point] = []
        for index in range(1, len(padded) - 2):
            p0, p1, p2, p3 = padded[index - 1], padded[index], padded[index + 1], padded[index + 2]
            for step in range(steps):
                t = step / steps
                curve.append(tuple(0.5 * ((2 * p1[axis]) + (-p0[axis] + p2[axis]) * t + (2 * p0[axis] - 5 * p1[axis] + 4 * p2[axis] - p3[axis]) * t * t
                                          + (-p0[axis] + 3 * p1[axis] - 3 * p2[axis] + p3[axis]) * t ** 3) for axis in (0, 1)))  # type: ignore[arg-type]
        return [*curve, points[-1]]

    def flow(self, points: list[Point], **style: float) -> None:
        self.line(self.sample(points), **style)

    def dots(self, spots: list[Point], size: float = 1.8) -> None:
        for x, y in spots:
            self._stroke([(x, y), (x + 0.4, y + 0.3)], size * 1.6, 0.7, 0.2)

    def arc(self, cx: float, cy: float, rx: float, ry: float, start: float, end: float, **style: float) -> None:
        steps = max(5, int(abs(end - start) * max(rx, ry) / 5))
        self.line([(cx + math.cos(start + (end - start) * step / steps) * rx, cy - math.sin(start + (end - start) * step / steps) * ry)
                   for step in range(steps + 1)], **style)

    def circle(self, cx: float, cy: float, radius: float, **style: float) -> None:
        self.arc(cx, cy, radius, radius, 0, math.tau * 1.04, **style)

    def box(self, left: float, top: float, right: float, bottom: float, **style: float) -> None:
        self.line([(left, top), (right, top), (right, bottom), (left, bottom), (left, top)], **style)

    def hatch(self, x: float, y: float, width: float, height: float, *, count: int, lean: float = 0.5,
              opacity: float = 0.35) -> None:
        for index in range(count):
            px = x + width * index / max(count - 1, 1) + self.random.uniform(-1.5, 1.5)
            length = height * self.random.uniform(0.55, 1)
            self.line([(px, y), (px - length * lean, y + length)], weight=0.7, opacity=opacity, shake=0.4, passes=1)

    def glow(self, cx: float, cy: float, radius: float) -> None:
        self.fills.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{GLOW}" opacity="0.7"/>')

    # --- sky -------------------------------------------------------------------------------------------------

    def sun(self, cx: float, cy: float, radius: float, *, rays: bool = False) -> None:
        self.glow(cx, cy, radius - 1)
        self.circle(cx, cy, radius, weight=0.9, opacity=0.5, shake=0.5)
        if rays:
            for index in range(10):
                angle = index / 10 * math.tau
                self.line([(cx + math.cos(angle) * (radius + 4), cy + math.sin(angle) * (radius + 4)),
                           (cx + math.cos(angle) * (radius + 9), cy + math.sin(angle) * (radius + 9))],
                          weight=0.7, opacity=0.4, shake=0.4, passes=1)

    def moon(self, cx: float, cy: float, radius: float) -> None:
        self.arc(cx, cy, radius, radius, math.pi * 0.42, math.pi * 1.58, weight=1.0, opacity=0.7, shake=0.4)
        self.arc(cx + radius * 0.55, cy, radius * 0.78, radius * 0.98, math.pi * 0.6, math.pi * 1.4, weight=0.9, opacity=0.7, shake=0.4)

    def stars(self, spots: list[Point]) -> None:
        for x, y in spots:
            size = self.random.uniform(1.6, 3.2)
            self.line([(x - size, y), (x + size, y)], weight=0.7, opacity=0.5, shake=0.2, passes=1)
            self.line([(x, y - size), (x, y + size)], weight=0.7, opacity=0.5, shake=0.2, passes=1)

    def cloud(self, cx: float, cy: float, width: float) -> None:
        bumps = [(-0.3, 0.2), (0.0, 0.3), (0.3, 0.22)]
        points: list[Point] = [(cx - width / 2, cy)]
        for offset, size in bumps:
            radius = width * size
            for step in range(7):
                angle = math.pi - step / 6 * math.pi
                points.append((cx + offset * width + math.cos(angle) * radius, cy - math.sin(angle) * radius * 0.8))
        points += [(cx + width / 2, cy), (cx - width / 2, cy)]
        self.line(points, weight=0.9, opacity=0.5, shake=0.6)
        self.hatch(cx + width * 0.05, cy - width * 0.12, width * 0.34, width * 0.1, count=5, lean=0.7, opacity=0.22)

    def birds(self, spots: list[Point], size: float = 5) -> None:
        for x, y in spots:
            s = size * self.random.uniform(0.8, 1.2)
            self.line([(x - s, y - s * 0.2), (x - s * 0.45, y - s * 0.6), (x, y), (x + s * 0.45, y - s * 0.6), (x + s, y - s * 0.2)],
                      weight=0.8, opacity=0.7, shake=0.3, passes=1)

    def balloon(self, cx: float, cy: float, radius: float) -> None:
        self.arc(cx, cy, radius, radius * 1.08, -math.pi * 0.22, math.pi * 1.22, weight=1.0)
        self.hatch(cx + radius * 0.3, cy - radius * 0.55, radius * 0.5, radius * 1.1, count=6, lean=0.18, opacity=0.28)
        self.rub([(cx + radius * 0.55, cy - radius * 0.5), (cx + radius * 0.5, cy + radius * 0.55)], radius * 0.45, 0.08)
        bottom = cy + radius * 1.35
        self.line([(cx - radius * 0.78, cy + radius * 0.7), (cx - radius * 0.22, bottom)], weight=1.0, shake=0.4)
        self.line([(cx + radius * 0.78, cy + radius * 0.7), (cx + radius * 0.22, bottom)], weight=1.0, shake=0.4)
        for lean in (-0.45, 0.0, 0.45):
            self.arc(cx, cy, radius * abs(lean) + 0.5, radius * 1.05, math.pi * 0.5, math.pi * (1.5 if lean <= 0 else -0.5),
                     weight=0.6, opacity=0.4, shake=0.3, passes=1)
        basket = radius * 0.3
        self.line([(cx - basket * 0.7, bottom), (cx - basket * 0.7, bottom + basket * 0.8)], weight=0.6, opacity=0.5, shake=0.2, passes=1)
        self.line([(cx + basket * 0.7, bottom), (cx + basket * 0.7, bottom + basket * 0.8)], weight=0.6, opacity=0.5, shake=0.2, passes=1)
        self.box(cx - basket, bottom + basket * 0.8, cx + basket, bottom + basket * 1.9, weight=1.0, shake=0.3)

    def smoke(self, x: float, y: float, height: float) -> None:
        self.line([(x + math.sin(step * 1.1) * (2 + step * 0.6), y - height * step / 7) for step in range(8)],
                  weight=0.7, opacity=0.4, shake=0.5, passes=1)

    # --- land and water --------------------------------------------------------------------------------------

    def ground(self, left: float, right: float, y: float, *, tufts: int = 8) -> None:
        self.line([(left, y), ((left + right) / 2, y - 2), (right, y)], weight=0.9, opacity=0.6, shake=1.2)
        for _ in range(max(2, tufts // 3)):
            self.hatch(self.random.uniform(left + 10, right - 24), y + 1.5, 16, 4.5, count=6, lean=1.6, opacity=0.26)
        for _ in range(tufts):
            px = self.random.uniform(left + 6, right - 6)
            self.line([(px, y + 1), (px + 2, y - 5)], weight=0.6, opacity=0.45, shake=0.5, passes=1)
            self.line([(px + 3, y + 1), (px + 6, y - 4)], weight=0.6, opacity=0.45, shake=0.5, passes=1)

    def mountains(self, peaks: list[Point], base: float, *, opacity: float = 0.5) -> None:
        def foot(peak: Point, side: int) -> Point:
            # The slope runs down to the base, or stops at the edge of the picture if that comes first.
            x, y = peak
            reach = (base - y) * 1.3
            room = (x - 3) if side < 0 else (self.width - 3 - x)
            share = min(1.0, room / reach)
            return (x + side * reach * share, y + (base - y) * share)

        ridge: list[Point] = []
        for index, (x, y) in enumerate(peaks):
            if index == 0:
                ridge.append(foot((x, y), -1))
            else:
                previous_x, previous_y = peaks[index - 1]
                ridge.append(((x + previous_x) / 2, max(y, previous_y) + (base - max(y, previous_y)) * 0.45))
            ridge.append((x, y))
        ridge.append(foot(peaks[-1], 1))
        self.line(ridge, weight=0.9, opacity=opacity, shake=1.1)
        for x, y in peaks:
            height = base - y
            if x + height * 0.5 < self.width - 6:
                self.rub([(x + 4, y + 7), (x + height * 0.42, y + height * 0.62)], max(5.0, height * 0.16), opacity * 0.16)
            # Strokes down the shaded side give each peak its weight.
            for stroke in range(8):
                offset = 4 + stroke * 3.6
                start, end = y + offset, min(y + offset * 1.9 + 8, base - 8)
                if end - start < 6 or x + offset * 0.5 + (end - start) * 0.62 > self.width - 4:
                    continue
                self.line([(x + offset * 0.5, start), (x + offset * 0.5 + (end - start) * 0.62, end)],
                          weight=0.6, opacity=opacity * 0.6, shake=0.7, passes=1)

    def waves(self, left: float, right: float, top: float, bottom: float, *, rows: int = 4, opacity: float = 0.5) -> None:
        for row in range(rows):
            y = top + (bottom - top) * row / max(rows - 1, 1)
            x = left + self.random.uniform(0, 14)
            while x < right - 12:
                length = self.random.uniform(10, 20)
                self.curve((x, y), (min(x + length, right), y), 2.2, weight=0.7, opacity=opacity, shake=0.4, passes=1)
                x += length + self.random.uniform(8, 18)

    def reeds(self, x: float, base: float, count: int, height: float = 26) -> None:
        for index in range(count):
            px = x + index * 6 + self.random.uniform(-2, 2)
            top = base - height * self.random.uniform(0.6, 1)
            self.line([(px, base), (px + self.random.uniform(-3, 3), top)], weight=0.8, opacity=0.7, shake=0.4, passes=1)
            self.line([(px - 0.5, top), (px + 0.5, top + 6)], weight=2.2, opacity=0.5, shake=0.3, passes=1)

    def path(self, points: list[Point], width: float = 7) -> None:
        count = len(points) - 1
        for side in (-1, 1):
            self.line([(x + side * width * (1 - index / count * 0.7) / 2, y) for index, (x, y) in enumerate(points)],
                      weight=0.7, opacity=0.4, shake=0.6, passes=1)

    def rocks(self, x: float, base: float, size: float) -> None:
        self.line([(x - size, base), (x - size * 0.6, base - size * 0.7), (x - size * 0.1, base - size), (x + size * 0.5, base - size * 0.6),
                   (x + size, base)], weight=1.0, opacity=0.7)
        self.hatch(x, base - size * 0.6, size * 0.6, size * 0.5, count=3, lean=0.3)

    # --- plants ----------------------------------------------------------------------------------------------

    def pine(self, x: float, base: float, height: float, *, opacity: float = 0.85) -> None:
        self.rub([(x + height * 0.05, base - height * 0.72), (x + height * 0.13, base - height * 0.1)], height * 0.16, opacity * 0.12)
        self.shadow(x + height * 0.1, base + 0.5, height * 0.42)
        self.line([(x, base), (x, base - height)], weight=1.0, opacity=opacity)
        tiers = max(5, int(height / 9))
        for tier in range(tiers):
            y = base - height + height * (tier + 0.6) / (tiers + 0.6)
            reach = height * 0.32 * (tier + 1) / tiers
            droop = reach * 0.55
            for side in (-1, 1):
                self.line([(x, y - droop), (x + side * reach * 0.55, y - droop * 0.35), (x + side * reach, y)],
                          weight=0.95, opacity=opacity, shake=0.8)
                if tier % 2:
                    self.line([(x + side * reach * 0.3, y - droop * 0.5), (x + side * reach * 0.75, y + 1.5)],
                              weight=0.6, opacity=opacity * 0.6, shake=0.6, passes=1)

    def tree(self, x: float, base: float, height: float, *, leaves: bool = True, droop: bool = False) -> None:
        trunk_top = base - height * 0.42
        if leaves and not droop:
            for lift, reach in ((0.3, 0.3), (0.42, 0.18), (0.2, 0.12)):
                self.rub([(x + height * (reach - 0.12), trunk_top - height * lift), (x + height * reach, trunk_top - height * (lift - 0.14))],
                         height * 0.13, 0.07)
        self.shadow(x + 10, base + 1.5, height * 0.4)
        self.line([(x - 9, base), (x - 5, base - height * 0.2), (x - 4, trunk_top)], weight=1.3)
        self.line([(x + 9, base), (x + 5, base - height * 0.2), (x + 4, trunk_top)], weight=1.3)
        self.hatch(x - 2, base - height * 0.38, 7, height * 0.36, count=4, lean=0.05, opacity=0.45)
        self.line([(x - 9, base), (x - 20, base + 4)], weight=1.0)
        self.line([(x + 9, base), (x + 22, base + 3)], weight=1.0)

        def branch(px: float, py: float, angle: float, length: float, depth: int) -> None:
            ex, ey = px + math.cos(angle) * length, py - math.sin(angle) * length
            self.line([(px, py), ((px + ex) / 2 + self.random.uniform(-2, 2), (py + ey) / 2), (ex, ey)],
                      weight=0.5 + depth * 0.22, shake=0.6)
            if depth == 0:
                if droop:
                    # A willow lets a long strand fall from every twig.
                    fall = height * self.random.uniform(0.3, 0.5)
                    self.line([(ex, ey), (ex + self.random.uniform(-3, 3), ey + fall * 0.5), (ex + self.random.uniform(-4, 4), ey + fall)],
                              weight=0.7, opacity=0.55, shake=0.8, passes=1)
                elif leaves:
                    for _ in range(3):
                        cx, cy = ex + self.random.uniform(-9, 9), ey + self.random.uniform(-7, 5)
                        radius = self.random.uniform(5, 9)
                        start = self.random.uniform(0, math.tau)
                        self.arc(cx, cy, radius, radius * 0.8, start, start + 3.6, weight=0.75, opacity=0.6, shake=0.7, passes=1)
                return
            for turn in (-0.5, 0.42):
                branch(ex, ey, angle + turn + self.random.uniform(-0.18, 0.18), length * 0.72, depth - 1)

        for angle, length in ((math.pi / 2 + 0.7, height * 0.2), (math.pi / 2 - 0.62, height * 0.21), (math.pi / 2 + 0.08, height * 0.24)):
            branch(x, trunk_top, angle, length, 3)

    def plant(self, x: float, base: float, size: float = 1.0) -> None:
        s = size
        self.line([(x - 8 * s, base - 12 * s), (x - 6 * s, base), (x + 6 * s, base), (x + 8 * s, base - 12 * s), (x - 8 * s, base - 12 * s)],
                  weight=1.0, shake=0.4)
        for lean, height in ((-0.9, 22), (-0.35, 30), (0.2, 34), (0.75, 24), (1.2, 16)):
            tip = (x + lean * 14 * s, base - 12 * s - height * s)
            self.line([(x, base - 12 * s), ((x + tip[0]) / 2 - lean * 2, base - 12 * s - height * s * 0.6), tip], weight=0.9, shake=0.5)
            self.arc(tip[0] - lean * 3 * s, tip[1] + 5 * s, 4 * s, 7 * s, 0.6, 3.4, weight=0.7, opacity=0.6, shake=0.4, passes=1)

    # --- buildings -------------------------------------------------------------------------------------------

    def tower(self, x: float, base: float, width: float, height: float, *, roof: float, flag: bool = False,
              windows: int = 1) -> None:
        left, right, top = x - width / 2, x + width / 2, base - height
        self.line([(left, base), (left, top)], weight=1.1)
        self.line([(right, base), (right, top)], weight=1.1)
        self.line([(left - 2, top), (right + 2, top)], weight=1.0)
        self.line([(left - 2, top), (x, top - roof), (right + 2, top)], weight=1.1)
        for window in range(windows):
            y = top + height * (0.2 + 0.6 * window / max(windows, 1))
            self.line([(x, y), (x, y + 5)], weight=1.0, shake=0.3)
        self.hatch(right - width * 0.42, top + 3, width * 0.38, height * 0.85, count=5, lean=0.06, opacity=0.38)
        self.rub([(right - width * 0.2, top + 2), (right - width * 0.2, base - 1)], width * 0.36, 0.1)
        self.hatch(x + width * 0.05, top - roof * 0.7, width * 0.4, roof * 0.6, count=3, lean=-0.5, opacity=0.3)
        if flag:
            self.line([(x, top - roof), (x, top - roof - 9)], weight=0.9, shake=0.3)
            self.line([(x, top - roof - 9), (x + 8, top - roof - 6.5), (x, top - roof - 4)], weight=0.9, shake=0.3)

    def palace(self, x: float, base: float, scale: float = 1.0) -> None:
        s = scale
        self.tower(x - 34 * s, base, 13 * s, 34 * s, roof=15 * s)
        self.tower(x + 36 * s, base, 13 * s, 30 * s, roof=14 * s)
        self.tower(x, base, 20 * s, 52 * s, roof=22 * s, flag=True)
        self.tower(x - 15 * s, base, 9 * s, 40 * s, roof=12 * s)
        self.tower(x + 17 * s, base, 9 * s, 43 * s, roof=12 * s)
        wall = base - 17 * s
        self.line([(x - 52 * s, base), (x - 52 * s, wall), (x + 54 * s, wall), (x + 54 * s, base)], weight=1.1)
        for notch in range(-5, 6):
            px = x + notch * 9.5 * s
            self.line([(px, wall), (px, wall - 3 * s), (px + 4.5 * s, wall - 3 * s), (px + 4.5 * s, wall)],
                      weight=0.8, shake=0.3, passes=1)
        self.line([(x - 5 * s, base), (x - 5 * s, base - 9 * s), (x, base - 13 * s), (x + 5 * s, base - 9 * s), (x + 5 * s, base)],
                  weight=1.0, shake=0.3)
        self.hatch(x + 10 * s, wall + 2 * s, 42 * s, 13 * s, count=9, lean=0.25, opacity=0.3)
        self.shadow(x + 14 * s, base + 2, 80 * s)

    def cottage(self, x: float, base: float, width: float, height: float, *, smoke: bool = False) -> None:
        left, right, eaves = x - width / 2, x + width / 2, base - height
        self.box(left, eaves, right, base, weight=1.0, shake=0.5)
        self.line([(left - 3, eaves), (x, eaves - height * 0.75), (right + 3, eaves)], weight=1.1, shake=0.5)
        self.box(x - width * 0.08, base - height * 0.55, x + width * 0.12, base, weight=0.8, shake=0.3, passes=1)
        self.box(left + width * 0.12, eaves + height * 0.25, left + width * 0.3, eaves + height * 0.55, weight=0.7, shake=0.3, passes=1)
        self.hatch(right - width * 0.36, eaves + 1.5, width * 0.32, height * 0.85, count=4, lean=0.12, opacity=0.34)
        self.hatch(x + width * 0.12, eaves - height * 0.5, width * 0.32, height * 0.42, count=4, lean=-0.9, opacity=0.3)
        chimney = x + width * 0.25
        self.line([(chimney, eaves - height * 0.3), (chimney, eaves - height * 0.8), (chimney + 4, eaves - height * 0.8), (chimney + 4, eaves - height * 0.18)],
                  weight=0.8, shake=0.3, passes=1)
        if smoke:
            self.smoke(chimney + 2, eaves - height * 0.85, height)

    def lighthouse(self, x: float, base: float, height: float) -> None:
        foot, neck, top = height * 0.16, height * 0.1, base - height
        self.line([(x - foot, base), (x - neck, top)], weight=1.1)
        self.line([(x + foot, base), (x + neck, top)], weight=1.1)
        for band in (0.3, 0.6):
            half = foot - (foot - neck) * band
            self.line([(x - half, base - height * band), (x + half, base - height * band)], weight=0.8, shake=0.4, passes=1)
        self.hatch(x - foot * 0.5, base - height * 0.28, foot * 1.1, height * 0.26, count=5, lean=0.1)
        self.rub([(x + neck * 0.5, top + 3), (x + foot * 0.55, base - 2)], foot * 0.7, 0.1)
        self.hatch(x + neck * 0.1, top + height * 0.42, neck * 0.9, height * 0.16, count=4, lean=0.08, opacity=0.34)
        self.line([(x - neck - 4, top), (x + neck + 4, top)], weight=1.1, shake=0.4)
        self.box(x - neck, top - height * 0.14, x + neck, top, weight=1.0, shake=0.4)
        self.line([(x - neck - 2, top - height * 0.14), (x, top - height * 0.27), (x + neck + 2, top - height * 0.14)], weight=1.1, shake=0.4)
        self.glow(x, top - height * 0.07, neck * 0.8)
        for side in (-1, 1):
            for spread in (-0.1, 0.05, 0.2):
                self.line([(x + side * (neck + 5), top - height * 0.07), (x + side * (neck + 34), top - height * (0.07 + spread))],
                          weight=0.6, opacity=0.3, shake=0.4, passes=1)

    def windmill(self, x: float, base: float, height: float) -> None:
        foot, neck, top = height * 0.2, height * 0.12, base - height
        self.line([(x - foot, base), (x - neck, top)], weight=1.1)
        self.line([(x + foot, base), (x + neck, top)], weight=1.1)
        self.line([(x - neck - 2, top), (x, top - height * 0.2), (x + neck + 2, top)], weight=1.1, shake=0.4)
        self.box(x - 2.5, base - height * 0.2, x + 2.5, base, weight=0.8, shake=0.3, passes=1)
        self.rub([(x + neck * 0.5, top + 3), (x + foot * 0.55, base - 2)], foot * 0.7, 0.1)
        self.hatch(x + neck * 0.2, top + height * 0.1, foot * 0.7, height * 0.8, count=5, lean=-0.08, opacity=0.32)
        hub = (x, top + height * 0.05)
        turn = self.random.uniform(0.2, 1.2)
        for blade in range(4):
            angle = turn + blade * math.pi / 2
            reach = height * 0.62
            tip = (hub[0] + math.cos(angle) * reach, hub[1] - math.sin(angle) * reach)
            self.line([hub, tip], weight=1.0, shake=0.4)
            side = (math.cos(angle + math.pi / 2) * height * 0.09, -math.sin(angle + math.pi / 2) * height * 0.09)
            start = (hub[0] + math.cos(angle) * reach * 0.3, hub[1] - math.sin(angle) * reach * 0.3)
            self.line([start, (start[0] + side[0], start[1] + side[1]), (tip[0] + side[0], tip[1] + side[1]), tip],
                      weight=0.7, opacity=0.6, shake=0.4, passes=1)

    def bridge(self, left: float, right: float, deck: float, *, arches: int, rise: float, floor: float) -> None:
        self.line([(left, deck), (right, deck)], weight=1.1)
        self.line([(left, deck - 5), (right, deck - 5)], weight=0.9, shake=0.5)
        span = (right - left) / arches
        for index in range(arches + 1):
            px = left + span * index
            self.line([(px, deck), (px, floor)], weight=1.0, shake=0.5)
            self.line([(px, deck - 5), (px, deck)], weight=0.7, shake=0.2, passes=1)
        for index in range(arches):
            cx = left + span * (index + 0.5)
            self.arc(cx, deck + rise, span * 0.42, rise * 0.82, 0, math.pi, weight=1.0, shake=0.5)
            self.hatch(cx - span * 0.3, deck + 2, span * 0.6, rise * 0.25, count=5, lean=0.2, opacity=0.3)

    def dome(self, x: float, base: float, radius: float) -> None:
        self.box(x - radius, base - radius * 0.7, x + radius, base, weight=1.1, shake=0.5)
        self.arc(x, base - radius * 0.7, radius, radius, 0, math.pi, weight=1.1, shake=0.5)
        self.arc(x, base - radius * 0.7, radius * 0.25, radius, math.pi * 0.5, math.pi * 0.02, weight=0.8, opacity=0.6, shake=0.3, passes=1)
        self.arc(x, base - radius * 0.7, radius * 0.25, radius, math.pi * 0.5, math.pi * 0.98, weight=0.8, opacity=0.6, shake=0.3, passes=1)
        self.hatch(x + radius * 0.35, base - radius * 1.45, radius * 0.6, radius * 1.35, count=6, lean=0.1, opacity=0.32)
        self.rub([(x + radius * 0.68, base - radius * 1.2), (x + radius * 0.7, base - 2)], radius * 0.5, 0.09)
        tip = (x + radius * 1.25, base - radius * 2.0)
        self.line([(x + radius * 0.3, base - radius * 1.45), tip], weight=1.6, opacity=0.7, shake=0.3)
        self.box(x - radius * 0.2, base - radius * 0.5, x + radius * 0.2, base, weight=0.8, shake=0.3, passes=1)

    def lantern(self, x: float, base: float, height: float) -> None:
        self.line([(x, base), (x, base - height)], weight=1.2, shake=0.4)
        self.line([(x - 4, base), (x + 4, base)], weight=1.0, shake=0.3)
        self.line([(x, base - height), (x + 9, base - height - 3)], weight=1.0, shake=0.3)
        self.box(x + 5, base - height - 3, x + 13, base - height + 8, weight=0.9, shake=0.3)
        self.line([(x + 4, base - height - 3), (x + 9, base - height - 8), (x + 14, base - height - 3)], weight=0.9, shake=0.3)
        self.glow(x + 9, base - height + 2.5, 3.2)

    def bench(self, x: float, base: float, width: float) -> None:
        left, right = x - width / 2, x + width / 2
        self.line([(left, base - 12), (right, base - 12)], weight=1.2, shake=0.4)
        self.line([(left, base - 24), (right, base - 24)], weight=1.0, shake=0.4)
        self.line([(left, base - 19), (right, base - 19)], weight=0.8, shake=0.4, passes=1)
        for px in (left + 3, right - 3):
            self.line([(px, base), (px, base - 25)], weight=1.0, shake=0.3)

    def fence(self, left: float, right: float, base: float, height: float = 12) -> None:
        for rail in (0.35, 0.75):
            self.line([(left, base - height * rail), (right, base - height * rail)], weight=0.8, opacity=0.6, shake=0.5, passes=1)
        posts = max(3, int((right - left) / 12))
        for index in range(posts + 1):
            px = left + (right - left) * index / posts
            self.line([(px, base), (px, base - height)], weight=0.9, opacity=0.7, shake=0.4, passes=1)

    def boat(self, x: float, y: float, scale: float = 1.0) -> None:
        s = scale
        self.line([(x - 10 * s, y), (x - 7 * s, y + 4 * s), (x + 7 * s, y + 4 * s), (x + 10 * s, y), (x - 10 * s, y)], weight=1.0, shake=0.4)
        self.line([(x, y), (x, y - 17 * s)], weight=0.9, shake=0.3)
        self.line([(x + 1 * s, y - 16 * s), (x + 9 * s, y - 3 * s), (x + 1 * s, y - 3 * s)], weight=1.0, shake=0.4)
        self.line([(x - 1.5 * s, y - 13 * s), (x - 7 * s, y - 3 * s), (x - 1.5 * s, y - 3 * s)], weight=0.9, shake=0.4)

    def tent(self, x: float, base: float, scale: float = 1.0) -> None:
        s = scale
        self.line([(x - 22 * s, base), (x, base - 30 * s), (x + 22 * s, base)], weight=1.1)
        self.line([(x, base - 30 * s), (x - 5 * s, base)], weight=0.9, shake=0.4)
        self.line([(x, base - 30 * s), (x + 5 * s, base)], weight=0.9, shake=0.4)
        self.line([(x, base - 30 * s), (x + 30 * s, base - 22 * s), (x + 22 * s, base)], weight=0.9, opacity=0.6, shake=0.5)
        self.hatch(x + 8 * s, base - 18 * s, 14 * s, 14 * s, count=4, lean=-0.4)

    def well(self, x: float, base: float) -> None:
        self.box(x - 16, base - 16, x + 16, base, weight=1.1, shake=0.5)
        for row in (5, 10):
            self.line([(x - 16, base - row), (x + 16, base - row)], weight=0.6, opacity=0.4, shake=0.4, passes=1)
        for px in (x - 13, x + 13):
            self.line([(px, base - 16), (px, base - 44)], weight=1.1, shake=0.4)
        self.line([(x - 20, base - 44), (x, base - 58), (x + 20, base - 44), (x - 20, base - 44)], weight=1.1, shake=0.5)
        self.line([(x - 13, base - 38), (x + 13, base - 38)], weight=0.8, shake=0.3)
        self.line([(x + 2, base - 38), (x + 2, base - 26)], weight=0.6, opacity=0.6, shake=0.2, passes=1)
        self.box(x - 2, base - 26, x + 6, base - 19, weight=0.8, shake=0.3, passes=1)

    def books(self, x: float, base: float, count: int) -> float:
        top = base
        for _ in range(count):
            width, thick = self.random.uniform(34, 48), self.random.uniform(6, 9)
            shift = self.random.uniform(-4, 4)
            self.box(x - width / 2 + shift, top - thick, x + width / 2 + shift, top, weight=1.0, shake=0.4)
            self.line([(x - width / 2 + shift + 5, top - thick), (x - width / 2 + shift + 5, top)], weight=0.6, opacity=0.5, shake=0.2, passes=1)
            top -= thick
        return top

    def shelf_books(self, left: float, base: float, count: int) -> None:
        x = left
        for _ in range(count):
            width, height = self.random.uniform(6, 11), self.random.uniform(26, 42)
            lean = self.random.choice((0, 0, 0, 2.5))
            self.line([(x, base), (x + lean, base - height), (x + lean + width, base - height), (x + width, base), (x, base)], weight=1.0, shake=0.3)
            self.line([(x + lean * 0.6 + 1, base - height * 0.7), (x + lean * 0.6 + width - 1, base - height * 0.7)],
                      weight=0.6, opacity=0.5, shake=0.2, passes=1)
            x += width + 1.5

    def hourglass(self, x: float, base: float, scale: float = 1.0) -> None:
        s = scale
        for y in (base, base - 34 * s):
            self.line([(x - 11 * s, y), (x + 11 * s, y)], weight=1.2, shake=0.3)
        self.line([(x - 9 * s, base - 34 * s), (x - 1.5 * s, base - 17 * s), (x - 9 * s, base)], weight=1.0, shake=0.4)
        self.line([(x + 9 * s, base - 34 * s), (x + 1.5 * s, base - 17 * s), (x + 9 * s, base)], weight=1.0, shake=0.4)
        self.hatch(x - 5 * s, base - 9 * s, 10 * s, 8 * s, count=5, lean=0.0, opacity=0.4)

    def candle(self, x: float, base: float) -> None:
        self.box(x - 3, base - 16, x + 3, base, weight=0.9, shake=0.3)
        self.line([(x, base - 16), (x, base - 20)], weight=0.6, shake=0.2, passes=1)
        self.glow(x, base - 24, 3)
        self.arc(x, base - 24, 2.4, 4.5, 0, math.tau, weight=0.7, opacity=0.6, shake=0.2, passes=1)

    def telescope(self, x: float, base: float, scale: float = 1.0) -> None:
        s = scale
        head = (x, base - 34 * s)
        for foot in (-14, 2, 15):
            self.line([head, (x + foot * s, base)], weight=1.0, shake=0.4)
        tip = (head[0] + 30 * s, head[1] - 24 * s)
        tail = (head[0] - 14 * s, head[1] + 11 * s)
        for side in (-2.6, 2.6):
            self.line([(tail[0] + side * 0.6 * s, tail[1] + side * 0.8 * s), (tip[0] + side * 0.6 * s, tip[1] + side * 0.8 * s)],
                      weight=1.1, shake=0.3)
        self.line([(tip[0] - 1.6 * s, tip[1] - 2.1 * s), (tip[0] + 1.6 * s, tip[1] + 2.1 * s)], weight=1.0, shake=0.2)
        self.line([(tail[0] - 1.6 * s, tail[1] - 2.1 * s), (tail[0] + 1.6 * s, tail[1] + 2.1 * s)], weight=1.0, shake=0.2)

    def arch_window(self, x: float, base: float, width: float, height: float) -> None:
        left, right, spring = x - width / 2, x + width / 2, base - height + width / 2
        for inset in (0, 4):
            self.line([(left + inset, base), (left + inset, spring)], weight=1.1 - inset * 0.05, shake=0.4)
            self.line([(right - inset, base), (right - inset, spring)], weight=1.1 - inset * 0.05, shake=0.4)
            self.arc(x, spring, width / 2 - inset, width / 2 - inset, 0, math.pi, weight=1.1 - inset * 0.05, shake=0.4)
        self.line([(left - 6, base), (right + 6, base)], weight=1.2, shake=0.4)
        self.line([(left - 6, base + 4), (right + 6, base + 4)], weight=0.9, shake=0.4)
        self.line([(x, base), (x, spring - width / 2 + 4)], weight=0.7, opacity=0.5, shake=0.3, passes=1)
        self.line([(left + 4, spring), (right - 4, spring)], weight=0.7, opacity=0.5, shake=0.3, passes=1)

    def door(self, x: float, base: float, width: float, height: float) -> None:
        left, right, spring = x - width / 2, x + width / 2, base - height + width / 2
        self.line([(left, base), (left, spring)], weight=1.1, shake=0.4)
        self.line([(right, base), (right, spring)], weight=1.1, shake=0.4)
        self.arc(x, spring, width / 2, width / 2, 0, math.pi, weight=1.1, shake=0.4)
        self.arc(x, spring, width / 2 + 5, width / 2 + 5, 0, math.pi, weight=0.8, opacity=0.6, shake=0.4)
        for plank in (0.25, 0.5, 0.75):
            self.line([(left + width * plank, base), (left + width * plank, spring - width * 0.4)], weight=0.6, opacity=0.4, shake=0.3, passes=1)
        self.circle(right - width * 0.18, base - height * 0.42, 1.8, weight=0.9, shake=0.2)
        for step in range(3):
            y, reach = base + step * 6, width / 2 + 6 + step * 7
            self.line([(x - reach, y), (x + reach, y)], weight=1.0, shake=0.5)
            self.line([(x - reach, y), (x - reach, y + 6)], weight=0.7, shake=0.2, passes=1)
            self.line([(x + reach, y), (x + reach, y + 6)], weight=0.7, shake=0.2, passes=1)

    def anchor(self, x: float, top: float, height: float) -> None:
        """A ship's anchor: ring, stock, shank, and two arms ending in flukes."""
        s = height / 106
        ring, bottom = top + 8 * s, top + height
        radius = 34 * s
        centre = bottom - radius
        self.circle(x, ring, 7 * s, weight=1.2, shake=0.4)
        self.circle(x, ring, 4.2 * s, weight=0.8, opacity=0.6, shake=0.3)
        for side in (-1, 1):
            self.line([(x + side * 2.6 * s, ring + 7 * s), (x + side * 3.4 * s, bottom - 5 * s)], weight=1.2, shake=0.4)
        stock = top + 28 * s
        self.box(x - 26 * s, stock - 2.6 * s, x + 26 * s, stock + 2.6 * s, weight=1.1, shake=0.4)
        for side in (-1, 1):
            self.circle(x + side * 28.5 * s, stock, 2.8 * s, weight=1.0, shake=0.2)
        for size, weight in ((radius, 1.3), (radius - 6 * s, 1.1)):
            self.arc(x, centre, size, size, math.pi * 1.08, math.pi * 1.92, weight=weight, shake=0.5)
        for side in (-1, 1):
            tip = (x + side * (radius + 2 * s), centre - 15 * s)
            self.line([tip, (x + side * (radius + 9 * s), centre + 5 * s), (x + side * (radius - 2 * s), centre + 8 * s),
                       (x + side * (radius - 10 * s), centre + 2 * s), tip], weight=1.2, shake=0.4)
            self.hatch(x + side * radius - 3 * s, centre - 6 * s, 9 * s, 11 * s, count=4, lean=0.3 * side, opacity=0.34)
        self.line([(x - 4 * s, bottom - 3 * s), (x, bottom + 4 * s), (x + 4 * s, bottom - 3 * s)], weight=1.1, shake=0.3)
        # The lit side is the left one: the right of the shank and the inside of the right arm are worked over.
        self.rub([(x + 1.6 * s, ring + 12 * s), (x + 2.2 * s, bottom - 10 * s)], 3.2 * s, 0.16)
        self.hatch(x + 4 * s, stock - 2 * s, 20 * s, 4.5 * s, count=7, lean=0.5, opacity=0.34)
        self.arc(x, centre, radius - 3 * s, radius - 3 * s, math.pi * 1.55, math.pi * 1.9, weight=2.0, opacity=0.14, shake=0.5, passes=1)

    def rope(self, points: list[Point]) -> None:
        self.line(points, weight=1.1, shake=0.5)
        self.line([(px + 2.4, py + 1.6) for px, py in points], weight=0.9, opacity=0.7, shake=0.5)
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            for step in range(1, max(2, int(math.hypot(x2 - x1, y2 - y1) / 5))):
                t = step / max(2, int(math.hypot(x2 - x1, y2 - y1) / 5))
                px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
                self.line([(px - 0.6, py - 0.8), (px + 2.8, py + 2.4)], weight=0.6, opacity=0.45, shake=0.2, passes=1)

    # --- output ----------------------------------------------------------------------------------------------

    def svg(self) -> str:
        paths = "\n".join(f'<path d="{"".join(parts)}" stroke-width="{weight}" opacity="{opacity}"/>'
                          for (weight, opacity), parts in sorted(self.strokes.items()))
        fills = "".join(fill + "\n" for fill in self.fills)
        light = f' opacity="{self.pressure}"' if self.pressure != 1 else ""
        # Paper is rough: the first step shakes the edge of every stroke, the second lets the grain show through it.
        grain = ('<defs><filter id="pencil" x="-2%" y="-2%" width="104%" height="104%">'
                 f'<feTurbulence type="fractalNoise" baseFrequency="0.55" numOctaves="2" seed="{self.grain}" result="tooth"/>'
                 '<feDisplacementMap in="SourceGraphic" in2="tooth" scale="1.7" xChannelSelector="R" yChannelSelector="G" result="line"/>'
                 f'<feTurbulence type="fractalNoise" baseFrequency="1.15" numOctaves="2" seed="{self.grain + 7}" result="paper"/>'
                 '<feColorMatrix in="paper" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -2.2 0 0 0 2.15" result="gaps"/>'
                 '<feComposite in="line" in2="gaps" operator="in"/></filter></defs>\n')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" '
                f'width="{self.width}" height="{self.height}">\n{grain}{fills}'
                f'<g fill="none" stroke="{GRAPHITE}" stroke-linecap="round" stroke-linejoin="round" filter="url(#pencil)"{light}>'
                f'\n{paths}\n</g>\n</svg>\n')


# --- hero-palace: beside the greeting on the home page (520 x 170) -------------------------------------------

def hero_palace_on_the_hill(s: Sketch) -> None:
    s.mountains([(70, 78), (150, 54), (235, 82)], 150, opacity=0.38)
    s.mountains([(390, 70), (455, 50), (505, 84)], 150, opacity=0.38)
    s.sun(352, 40, 21)
    s.curve((70, 160), (470, 160), 52, weight=1.1, opacity=0.8)
    s.palace(278, 110, 0.95)
    for x, height in ((118, 46), (140, 62), (163, 40), (402, 50), (424, 36), (96, 30)):
        s.pine(x, 152 + abs(270 - x) * 0.02, height)
    s.hatch(180, 126, 150, 22, count=16, lean=0.9, opacity=0.25)
    s.ground(40, 500, 163, tufts=12)


def hero_lighthouse(s: Sketch) -> None:
    s.sun(96, 58, 19, rays=True)
    s.cloud(205, 34, 58)
    s.cloud(300, 52, 40)
    s.line([(292, 163), (318, 132), (338, 104), (396, 98), (452, 102), (478, 126), (506, 163)], weight=1.1)
    s.hatch(322, 112, 26, 44, count=6, lean=0.35)
    s.hatch(470, 128, 24, 30, count=5, lean=-0.3)
    s.lighthouse(388, 99, 72)
    s.cottage(442, 102, 24, 13, smoke=True)
    s.waves(24, 300, 134, 160, rows=5)
    s.boat(150, 136, 1.7)
    s.boat(236, 146, 0.9)
    s.birds([(226, 76), (252, 62), (280, 80), (182, 88)])
    s.rocks(276, 163, 12)


def hero_observatory(s: Sketch) -> None:
    s.mountains([(110, 66), (205, 42), (300, 74)], 150, opacity=0.4)
    s.moon(92, 36, 16)
    s.stars([(150, 22), (184, 48), (248, 20), (296, 40), (332, 18), (372, 52), (424, 28), (466, 60), (40, 70), (488, 26)])
    s.curve((150, 162), (500, 162), 60, weight=1.1, opacity=0.8)
    s.dome(336, 104, 24)
    s.tower(384, 112, 12, 26, roof=11)
    s.path([(300, 162), (322, 142), (316, 124), (332, 106)], 9)
    for x, height in ((204, 40), (226, 56), (250, 34), (432, 44), (456, 30)):
        s.pine(x, 152, height)
    s.ground(30, 505, 163, tufts=10)


def hero_bridge(s: Sketch) -> None:
    s.mountains([(238, 60), (300, 46)], 130, opacity=0.3)
    s.curve((14, 163), (206, 163), 58, weight=1.1, opacity=0.8)
    s.curve((318, 163), (508, 163), 62, weight=1.1, opacity=0.8)
    s.bridge(146, 376, 112, arches=3, rise=28, floor=158)
    s.tower(146, 112, 14, 30, roof=13, flag=True)
    s.tower(376, 112, 14, 30, roof=13)
    s.waves(160, 366, 146, 160, rows=3)
    for x, height in ((56, 40), (82, 54), (428, 50), (452, 36), (476, 44)):
        s.pine(x, 150, height)
    s.cottage(108, 124, 22, 13, smoke=True)
    s.birds([(214, 30), (244, 22), (330, 34)])
    s.sun(420, 34, 15)


def hero_island_in_the_clouds(s: Sketch) -> None:
    s.line([(176, 96), (200, 116), (222, 122), (238, 140), (262, 154), (282, 134), (302, 124), (324, 110), (344, 96)], weight=1.1)
    s.hatch(206, 100, 120, 26, count=14, lean=0.2, opacity=0.3)
    s.line([(172, 96), (260, 92), (348, 96)], weight=1.1, opacity=0.8)
    s.palace(260, 94, 0.72)
    s.pine(196, 96, 22)
    s.pine(326, 96, 26)
    s.line([(238, 140), (236, 163)], weight=0.6, opacity=0.4, shake=0.8, passes=1)
    s.line([(242, 142), (243, 160)], weight=0.6, opacity=0.4, shake=0.8, passes=1)
    s.cloud(88, 128, 86)
    s.cloud(420, 140, 96)
    s.cloud(130, 48, 54)
    s.cloud(262, 163, 70)
    s.balloon(430, 62, 20)
    s.balloon(72, 66, 12)
    s.birds([(160, 76), (372, 40), (392, 52)])
    s.sun(352, 30, 14)


def hero_palace_by_the_lake(s: Sketch) -> None:
    s.mountains([(90, 64), (170, 46)], 118, opacity=0.34)
    s.mountains([(420, 58), (480, 72)], 118, opacity=0.34)
    s.sun(232, 34, 16)
    s.line([(40, 118), (270, 115), (500, 118)], weight=1.0, opacity=0.7, shake=1.0)
    s.palace(322, 116, 0.82)
    for x, height in ((396, 34), (416, 44), (244, 30), (224, 22)):
        s.pine(x, 117, height)
    for row in range(5):
        y = 126 + row * 6
        width = 48 - row * 7
        s.line([(322 - width, y), (322 + width, y)], weight=0.7, opacity=0.3 - row * 0.03, shake=1.4, passes=1)
    s.waves(44, 496, 128, 160, rows=5, opacity=0.4)
    s.boat(140, 138, 1.5)
    s.reeds(60, 165, 6)
    s.reeds(446, 166, 5, 22)
    s.birds([(122, 52), (146, 40)])


def hero_windmill_village(s: Sketch) -> None:
    s.cloud(120, 36, 60)
    s.cloud(388, 30, 48)
    s.sun(300, 34, 15, rays=True)
    s.curve((30, 163), (492, 163), 44, weight=1.1, opacity=0.8)
    s.windmill(152, 132, 62)
    s.cottage(236, 122, 26, 15, smoke=True)
    s.cottage(278, 120, 22, 13)
    s.cottage(326, 123, 28, 16, smoke=True)
    s.windmill(410, 136, 44)
    s.fence(184, 222, 128)
    s.fence(350, 386, 132)
    s.path([(262, 163), (250, 148), (268, 134), (258, 122)], 10)
    s.pine(96, 146, 34)
    s.pine(456, 150, 30)
    s.birds([(204, 52), (226, 44), (350, 60)])
    s.ground(20, 505, 164, tufts=10)


def hero_tower_of_birds(s: Sketch) -> None:
    s.mountains([(86, 74), (160, 56)], 150, opacity=0.34)
    s.mountains([(410, 62), (470, 80)], 150, opacity=0.34)
    s.curve((90, 162), (450, 162), 46, weight=1.1, opacity=0.8)
    s.tower(270, 118, 26, 84, roof=24, flag=True, windows=4)
    s.tower(238, 118, 14, 38, roof=13)
    s.tower(304, 118, 14, 46, roof=13)
    s.line([(222, 118), (222, 104), (320, 104), (320, 118)], weight=1.0)
    s.birds([(218, 30), (236, 18), (300, 14), (318, 28), (330, 46), (204, 50), (250, 44)], 4.5)
    s.path([(184, 162), (214, 146), (230, 132), (258, 120)], 10)
    s.lantern(194, 150, 22)
    s.lantern(236, 130, 18)
    for x, height in ((128, 42), (150, 30), (372, 48), (396, 34)):
        s.pine(x, 152, height)
    s.ground(40, 500, 163, tufts=10)


# --- sidebar-tree: under the menu (216 x 180) ------------------------------------------------------------------

def sidebar_old_tree(s: Sketch) -> None:
    s.mountains([(150, 96), (196, 82)], 140, opacity=0.3)
    s.palace(172, 136, 0.32)
    s.pine(140, 146, 20, opacity=0.6)
    s.pine(203, 148, 24, opacity=0.6)
    s.tree(72, 158, 132)
    s.ground(8, 210, 161, tufts=9)


def sidebar_camp(s: Sketch) -> None:
    s.moon(168, 34, 13)
    s.stars([(40, 30), (84, 18), (118, 46), (196, 70), (22, 74), (140, 20)])
    for x, height in ((28, 74), (54, 96), (176, 84), (200, 58)):
        s.pine(x, 152, height)
    s.tent(112, 158, 1.25)
    s.line([(150, 158), (158, 150), (166, 158)], weight=1.0, shake=0.4)
    s.line([(152, 158), (164, 152)], weight=0.9, shake=0.4)
    s.glow(158, 150, 4)
    s.smoke(158, 146, 40)
    s.ground(8, 210, 161, tufts=7)


def sidebar_swing(s: Sketch) -> None:
    s.cloud(160, 34, 46)
    s.tree(84, 158, 136)
    s.line([(118, 74), (120, 128)], weight=0.7, opacity=0.7, shake=0.4)
    s.line([(136, 70), (138, 128)], weight=0.7, opacity=0.7, shake=0.4)
    s.line([(116, 128), (142, 128)], weight=1.3, shake=0.3)
    s.birds([(172, 62), (190, 52), (150, 84)], 4.5)
    s.curve((120, 161), (212, 161), 10, weight=0.9, opacity=0.6)
    s.ground(8, 210, 161, tufts=10)


def sidebar_winter(s: Sketch) -> None:
    s.moon(48, 36, 14)
    s.stars([(96, 20), (132, 40), (176, 22), (198, 56), (20, 80), (160, 70)])
    s.tree(88, 158, 128, leaves=False)
    s.cottage(170, 156, 30, 16, smoke=True)
    s.curve((6, 162), (112, 162), 7, weight=0.9, opacity=0.6)
    s.curve((104, 163), (212, 163), 6, weight=0.9, opacity=0.6)
    s.pine(204, 156, 26, opacity=0.6)


def sidebar_willow_and_bench(s: Sketch) -> None:
    s.tree(70, 158, 130, droop=True)
    s.bench(138, 158, 46)
    s.lantern(184, 158, 74)
    s.birds([(150, 46), (168, 36)], 4.5)
    s.ground(8, 210, 161, tufts=9)


def sidebar_well(s: Sketch) -> None:
    s.mountains([(60, 92), (110, 78)], 140, opacity=0.28)
    s.pine(30, 152, 50, opacity=0.6)
    s.pine(52, 154, 34, opacity=0.6)
    s.well(118, 158)
    s.birds([(104, 92), (132, 88), (176, 60)], 4.5)
    s.fence(152, 208, 158)
    s.path([(96, 178), (104, 168), (112, 160)], 12)
    s.plant(182, 158, 0.7)
    s.ground(8, 210, 161, tufts=8)


def sidebar_reading_table(s: Sketch) -> None:
    s.line([(14, 150), (204, 150)], weight=1.3, shake=0.6)
    s.line([(22, 150), (22, 176)], weight=1.1, shake=0.4)
    s.line([(196, 150), (196, 176)], weight=1.1, shake=0.4)
    top = s.books(74, 150, 5)
    s.candle(74, top)
    s.hourglass(134, 150, 1.25)
    s.plant(178, 150, 1.0)
    s.arch_window(108, 78, 60, 62)
    s.moon(118, 42, 8)
    s.stars([(94, 34), (100, 56)])


# --- heading-mountains: along the end of a page heading, a long strip of horizon (720 x 96) -------------------

def heading_range(s: Sketch) -> None:
    s.mountains([(60, 46), (118, 30), (176, 50), (238, 24), (300, 44), (356, 36), (420, 50), (486, 28), (548, 46), (612, 34), (668, 50)],
                84, opacity=0.5)
    for x, height in ((34, 20), (148, 16), (212, 22), (330, 18), (392, 24), (458, 18), (520, 22), (590, 16), (694, 22)):
        s.pine(x, 88, height, opacity=0.7)
    s.birds([(270, 14), (288, 8), (560, 16)], 4)
    s.ground(6, 714, 89, tufts=16)


def heading_windmills(s: Sketch) -> None:
    s.curve((0, 89), (260, 89), 22, weight=1.0, opacity=0.7)
    s.curve((200, 89), (480, 89), 26, weight=1.0, opacity=0.7)
    s.curve((430, 89), (720, 89), 22, weight=1.0, opacity=0.7)
    s.windmill(96, 72, 36)
    s.windmill(262, 68, 42)
    s.windmill(356, 70, 30)
    s.windmill(528, 72, 38)
    s.windmill(644, 76, 32)
    s.cottage(170, 80, 18, 10)
    s.cottage(446, 80, 18, 10, smoke=True)
    s.cottage(590, 78, 16, 9)
    s.birds([(40, 26), (58, 18), (206, 22), (316, 20), (480, 24), (690, 30)], 4)
    s.cloud(150, 24, 40)
    s.cloud(420, 20, 44)
    s.cloud(606, 26, 36)
    s.ground(6, 714, 90, tufts=12)


def heading_sea(s: Sketch) -> None:
    s.line([(6, 60), (360, 59), (714, 60)], weight=0.9, opacity=0.6, shake=0.6)
    s.glow(362, 58, 15)
    s.arc(362, 59, 16, 16, 0, math.pi, weight=0.9, opacity=0.6, shake=0.4)
    for index in range(7):
        angle = math.pi * (index + 0.5) / 7
        s.line([(362 + math.cos(angle) * 21, 59 - math.sin(angle) * 21), (362 + math.cos(angle) * 28, 59 - math.sin(angle) * 28)],
               weight=0.7, opacity=0.4, shake=0.3, passes=1)
    s.waves(10, 710, 66, 90, rows=4)
    s.boat(92, 62, 1.1)
    s.boat(250, 72, 1.5)
    s.boat(156, 78, 0.7)
    s.boat(476, 64, 1.0)
    s.boat(566, 74, 1.6)
    s.boat(660, 62, 0.9)
    s.birds([(60, 28), (78, 20), (300, 26), (430, 18), (520, 30), (690, 22)], 4)
    s.cloud(180, 26, 40)
    s.cloud(600, 24, 44)


def heading_forest(s: Sketch) -> None:
    s.moon(640, 24, 11)
    s.stars([(30, 16), (96, 26), (160, 12), (228, 22), (290, 14), (360, 26), (430, 12), (500, 22), (566, 14), (700, 40)])
    x = 16.0
    while x < 708:
        s.pine(x, 88, s.random.uniform(18, 54), opacity=s.random.uniform(0.6, 0.85))
        x += s.random.uniform(15, 27)
    s.ground(6, 714, 89, tufts=9)


def heading_balloons(s: Sketch) -> None:
    s.curve((0, 90), (250, 90), 14, weight=1.0, opacity=0.6)
    s.curve((200, 90), (490, 90), 18, weight=1.0, opacity=0.6)
    s.curve((440, 90), (720, 90), 15, weight=1.0, opacity=0.6)
    s.balloon(88, 34, 14)
    s.balloon(214, 26, 17)
    s.balloon(332, 40, 12)
    s.balloon(456, 28, 15)
    s.balloon(566, 40, 12)
    s.balloon(664, 24, 16)
    s.cloud(150, 60, 44)
    s.cloud(280, 22, 36)
    s.cloud(394, 66, 40)
    s.cloud(516, 64, 42)
    s.cloud(612, 62, 34)
    s.pine(40, 84, 16, opacity=0.6)
    s.pine(262, 80, 14, opacity=0.6)
    s.pine(480, 80, 16, opacity=0.6)
    s.pine(700, 84, 14, opacity=0.6)
    s.birds([(26, 30), (300, 58), (420, 16), (700, 52)], 4)


def heading_village(s: Sketch) -> None:
    s.tower(68, 88, 12, 40, roof=13, flag=True)
    s.cottage(104, 88, 22, 14, smoke=True)
    s.cottage(136, 88, 18, 18)
    s.cottage(170, 88, 26, 13)
    s.tower(206, 88, 14, 52, roof=15, windows=2)
    s.cottage(244, 88, 24, 16, smoke=True)
    s.cottage(280, 88, 18, 12)
    s.cottage(314, 88, 26, 18)
    s.tower(350, 88, 10, 32, roof=11)
    s.pine(384, 88, 28, opacity=0.7)
    s.cottage(422, 88, 22, 14)
    s.cottage(458, 88, 26, 17, smoke=True)
    s.tower(496, 88, 12, 44, roof=13, windows=2)
    s.cottage(532, 88, 20, 13)
    s.windmill(580, 88, 42)
    s.cottage(628, 88, 24, 15, smoke=True)
    s.tower(662, 88, 10, 30, roof=11, flag=True)
    s.pine(30, 88, 26, opacity=0.7)
    s.pine(696, 88, 30, opacity=0.7)
    s.birds([(150, 26), (170, 18), (290, 30), (420, 20), (540, 26)], 4)
    s.ground(6, 714, 89, tufts=10)


def heading_river(s: Sketch) -> None:
    s.line([(6, 66), (252, 64)], weight=1.0, opacity=0.7, shake=0.8)
    s.line([(470, 64), (714, 66)], weight=1.0, opacity=0.7, shake=0.8)
    s.bridge(252, 470, 62, arches=4, rise=17, floor=86)
    s.waves(244, 478, 80, 92, rows=3)
    s.reeds(228, 70, 4, 16)
    s.reeds(474, 70, 4, 16)
    for x, height in ((30, 30), (56, 40), (84, 24), (124, 34), (154, 26), (192, 38), (514, 36), (544, 26), (576, 42), (612, 30),
                      (646, 38), (686, 28)):
        s.pine(x, 66, height, opacity=0.75)
    s.birds([(330, 22), (352, 14), (384, 26)], 4)
    s.sun(40, 20, 9)
    s.cloud(600, 18, 40)


def heading_night_watch(s: Sketch) -> None:
    s.mountains([(70, 48), (150, 30), (226, 52), (300, 36), (372, 50)], 84, opacity=0.42)
    s.moon(470, 22, 11)
    s.stars([(20, 14), (58, 24), (108, 12), (190, 16), (260, 12), (336, 18), (410, 14), (520, 12), (560, 30), (620, 16), (668, 34),
             (704, 18)])
    s.curve((440, 89), (720, 89), 22, weight=1.0, opacity=0.7)
    s.dome(590, 70, 16)
    s.tower(636, 74, 10, 22, roof=10)
    s.pine(500, 84, 18, opacity=0.7)
    s.pine(540, 80, 22, opacity=0.7)
    s.pine(676, 82, 20, opacity=0.7)
    s.ground(6, 714, 89, tufts=12)


# --- margin-doodle: what a hand draws in the margin while the mind is elsewhere (120 x 120) --------------------

def doodle_spiral(s: Sketch) -> None:
    s.flow([(60 + math.cos(turn / 9 * math.tau) * (2 + turn * 0.95), 60 + math.sin(turn / 9 * math.tau) * (2 + turn * 0.95))
            for turn in range(44)], weight=1.0, shake=0.5)


def doodle_stars(s: Sketch) -> None:
    for cx, cy, radius, start in ((42, 46, 28, -1.57), (88, 86, 15, -1.2), (92, 28, 9, -1.8)):
        s.line([(cx + math.cos(start + step * math.tau * 2 / 5) * radius, cy + math.sin(start + step * math.tau * 2 / 5) * radius)
                for step in range(6)], weight=1.0, shake=0.7)
    s.dots([(20, 92), (30, 104), (64, 100)])


def doodle_arrow(s: Sketch) -> None:
    s.flow([(14, 94), (34, 74), (54, 58), (60, 40), (48, 30), (38, 42), (50, 56), (74, 56), (92, 44), (104, 26)], weight=1.1, shake=0.5)
    s.line([(90, 26), (105, 25), (104, 41)], weight=1.1, shake=0.4)


def doodle_cube(s: Sketch) -> None:
    s.box(26, 48, 74, 96, weight=1.1, shake=0.6)
    s.box(48, 26, 96, 74, weight=1.0, shake=0.6)
    for x, y in ((26, 48), (74, 48), (26, 96), (74, 96)):
        s.line([(x, y), (x + 22, y - 22)], weight=1.0, shake=0.5)
    s.hatch(78, 52, 16, 40, count=6, lean=0.5, opacity=0.4)


def doodle_flower(s: Sketch) -> None:
    for petal in range(7):
        angle = petal / 7 * math.tau
        s.arc(60 + math.cos(angle) * 17, 44 - math.sin(angle) * 17, 10, 7, angle, angle + math.tau * 1.05, weight=0.9, shake=0.5)
    s.circle(60, 44, 6, weight=1.0, shake=0.4)
    s.flow([(60, 62), (56, 80), (60, 96), (58, 112)], weight=1.1, shake=0.5)
    s.flow([(58, 90), (42, 80), (34, 86), (46, 94), (58, 92)], weight=0.9, shake=0.5)


def doodle_face(s: Sketch) -> None:
    s.circle(60, 62, 36, weight=1.1, shake=0.8)
    s.arc(47, 54, 4, 5, 0, math.tau, weight=1.0, shake=0.3)
    s.arc(73, 54, 4, 5, 0, math.tau, weight=1.0, shake=0.3)
    s.arc(60, 68, 18, 13, math.pi * 1.12, math.pi * 1.88, weight=1.1, shake=0.5)
    for lock in range(5):
        s.flow([(44 + lock * 8, 28), (42 + lock * 8, 18), (48 + lock * 8, 12)], weight=0.8, opacity=0.7, shake=0.6)


def doodle_noughts_and_crosses(s: Sketch) -> None:
    for position in (46, 76):
        s.line([(position, 16), (position, 106)], weight=1.1, shake=0.8)
        s.line([(16, position), (106, position)], weight=1.1, shake=0.8)
    for cx, cy in ((30, 30), (61, 61), (92, 92)):
        s.line([(cx - 8, cy - 8), (cx + 8, cy + 8)], weight=1.0, shake=0.6)
        s.line([(cx + 8, cy - 8), (cx - 8, cy + 8)], weight=1.0, shake=0.6)
    for cx, cy in ((92, 30), (30, 61), (61, 92)):
        s.circle(cx, cy, 8.5, weight=1.0, shake=0.6)
    s.line([(18, 18), (104, 104)], weight=0.8, opacity=0.6, shake=1.2)


def doodle_paper_plane(s: Sketch) -> None:
    s.line([(22, 66), (104, 26), (66, 98), (56, 74), (22, 66)], weight=1.1, shake=0.6)
    s.line([(104, 26), (56, 74)], weight=0.9, shake=0.5)
    s.line([(56, 74), (60, 90), (66, 98)], weight=0.8, opacity=0.7, shake=0.4)
    trail = s.sample([(48, 92), (34, 104), (20, 100), (16, 88), (26, 84)])
    for index in range(0, len(trail) - 2, 4):
        s.line([trail[index], trail[index + 2]], weight=0.8, opacity=0.6, shake=0.3, passes=1)


def doodle_lightbulb(s: Sketch) -> None:
    s.arc(60, 48, 26, 26, -math.pi * 0.28, math.pi * 1.28, weight=1.1, shake=0.6)
    s.line([(42, 67), (48, 82), (72, 82), (78, 67)], weight=1.0, shake=0.5)
    for y in (88, 94):
        s.line([(49, y), (71, y)], weight=1.0, shake=0.5)
    s.line([(54, 100), (66, 100)], weight=1.0, shake=0.4)
    s.line([(50, 82), (54, 58), (58, 68), (62, 58), (66, 68), (70, 82)], weight=0.8, opacity=0.7, shake=0.5)
    for index in range(7):
        angle = math.pi * (index - 0.5) / 5.5
        s.line([(60 + math.cos(angle) * 34, 48 - math.sin(angle) * 34), (60 + math.cos(angle) * 43, 48 - math.sin(angle) * 43)],
               weight=0.8, opacity=0.6, shake=0.4, passes=1)


def doodle_scribble(s: Sketch) -> None:
    s.line([(20 + step * 4.2, 34 if step % 2 else 82) for step in range(20)], weight=0.9, shake=1.4)
    s.line([(24, 96 + (step % 2) * 9) if step % 2 else (24 + step * 4.0, 96) for step in range(1, 20)], weight=0.8, opacity=0.7, shake=1.0)
    s.flow([(16, 22), (40, 14), (70, 20), (100, 14)], weight=0.9, opacity=0.7, shake=0.8)


def doodle_cup(s: Sketch) -> None:
    s.line([(32, 56), (38, 94), (76, 94), (82, 56), (32, 56)], weight=1.1, shake=0.6)
    s.arc(84, 72, 12, 12, math.pi * 0.5, -math.pi * 0.5, weight=1.0, shake=0.5)
    s.arc(57, 100, 36, 6, 0, math.tau, weight=0.9, opacity=0.7, shake=0.6)
    for x in (46, 58, 70):
        s.flow([(x, 48), (x - 4, 38), (x + 4, 28), (x - 2, 16)], weight=0.8, opacity=0.6, shake=0.6)
    s.hatch(62, 60, 14, 30, count=5, lean=0.1, opacity=0.35)


def doodle_marks(s: Sketch) -> None:
    s.flow([(22, 42), (26, 24), (44, 18), (56, 32), (46, 48), (38, 58), (38, 72)], weight=1.2, shake=0.5)
    s.dots([(38, 86)], 2.4)
    s.line([(84, 20), (82, 72)], weight=1.3, shake=0.6)
    s.dots([(82, 86)], 2.4)
    s.dots([(40, 106), (52, 106), (64, 106)], 1.6)
    s.flow([(74, 104), (86, 100), (98, 106), (108, 100)], weight=0.9, opacity=0.7, shake=0.5)


def doodle_eye(s: Sketch) -> None:
    s.arc(60, 76, 46, 30, math.pi * 0.16, math.pi * 0.84, weight=1.1, shake=0.6)
    s.arc(60, 44, 46, 30, math.pi * 1.16, math.pi * 1.84, weight=1.1, shake=0.6)
    s.circle(60, 60, 13, weight=1.0, shake=0.5)
    s.circle(60, 60, 5, weight=1.6, shake=0.3)
    s.hatch(52, 50, 16, 9, count=6, lean=0.3, opacity=0.4)
    for index in range(6):
        x = 30 + index * 12
        lift = 46 - math.sin(index / 5 * math.pi) * 14
        s.line([(x, lift), (x - 3 + index, lift - 9)], weight=0.8, opacity=0.7, shake=0.4, passes=1)


def doodle_house(s: Sketch) -> None:
    s.cottage(54, 100, 54, 34, smoke=True)
    s.sun(98, 24, 9, rays=True)
    s.line([(12, 101), (110, 100)], weight=0.9, opacity=0.7, shake=0.9)
    s.flow([(88, 100), (90, 86), (96, 80), (102, 86), (100, 100)], weight=0.9, shake=0.5)
    s.birds([(26, 28), (40, 20)], 4)


def doodle_loops(s: Sketch) -> None:
    for scale in (1.0, 0.82, 1.12):
        s.flow([(60 + math.sin(step / 18 * math.tau) * 40 * scale, 54 + math.sin(step / 9 * math.tau) * 18 * scale) for step in range(20)],
               weight=0.9, shake=0.8, passes=1)
    s.flow([(18, 96), (32, 88), (44, 100), (58, 88), (72, 100), (86, 88), (102, 98)], weight=1.0, shake=0.6)


def doodle_squares(s: Sketch) -> None:
    for step in range(5):
        half, turn = 42 - step * 8, step * 0.2
        s.line([(60 + math.cos(turn + corner * math.pi / 2 + math.pi / 4) * half * 1.3, 60 + math.sin(turn + corner * math.pi / 2 + math.pi / 4) * half * 1.3)
                for corner in range(5)], weight=1.0 - step * 0.05, shake=0.6)


# --- card-window: at the edge of a card and in an empty box (200 x 140) ----------------------------------------

def card_pines(s: Sketch) -> None:
    s.mountains([(76, 58), (128, 40)], 118, opacity=0.36)
    for x, height in ((132, 86), (158, 64), (108, 52), (178, 44)):
        s.pine(x, 128, height)
    s.hatch(96, 118, 90, 10, count=12, lean=0.8, opacity=0.25)
    s.ground(70, 196, 130, tufts=7)


def card_window(s: Sketch) -> None:
    s.arch_window(100, 122, 86, 104)
    s.line([(64, 108), (82, 84), (94, 96), (112, 72), (136, 106)], weight=0.8, opacity=0.5, shake=0.7)
    s.sun(124, 52, 8)
    s.birds([(80, 56), (92, 50)], 3.5)
    s.plant(68, 122, 0.55)


def card_door(s: Sketch) -> None:
    s.door(92, 108, 46, 78)
    s.lantern(150, 126, 66)
    s.plant(44, 126, 0.8)
    s.hatch(124, 60, 16, 40, count=4, lean=0.1, opacity=0.25)
    s.hatch(48, 46, 14, 44, count=4, lean=0.1, opacity=0.25)


def card_balloon(s: Sketch) -> None:
    s.balloon(104, 52, 30)
    s.cloud(52, 116, 64)
    s.cloud(152, 124, 66)
    s.cloud(160, 34, 38)
    s.birds([(36, 46), (50, 38), (170, 70)], 4)


def card_sailboat(s: Sketch) -> None:
    s.sun(158, 36, 13, rays=True)
    s.boat(98, 98, 2.5)
    s.waves(18, 186, 108, 132, rows=4)
    s.birds([(40, 40), (56, 32)], 4)
    s.cloud(72, 26, 40)


def card_shelf(s: Sketch) -> None:
    s.line([(24, 112), (182, 112)], weight=1.3, shake=0.5)
    s.line([(24, 116), (182, 116)], weight=0.9, shake=0.5)
    for x in (44, 162):
        s.line([(x, 116), (x, 128), (x + 10, 116)], weight=0.9, shake=0.3)
    s.shelf_books(36, 112, 8)
    s.plant(150, 112, 1.0)
    s.hourglass(116, 112, 0.75)
    s.line([(24, 54), (182, 54)], weight=1.0, opacity=0.6, shake=0.5)
    s.shelf_books(96, 54, 6)
    s.candle(60, 54)


def card_stargazer(s: Sketch) -> None:
    s.moon(160, 30, 13)
    s.stars([(30, 24), (62, 44), (96, 18), (124, 50), (184, 66), (26, 70), (140, 14)])
    s.curve((10, 130), (192, 130), 12, weight=1.0, opacity=0.7)
    s.telescope(88, 124, 1.5)
    s.pine(170, 124, 34, opacity=0.7)
    s.pine(30, 126, 24, opacity=0.7)


def card_anchor(s: Sketch) -> None:
    s.rope([(108, 15), (126, 7), (148, 10), (164, 24), (170, 44), (162, 62), (172, 82), (186, 92)])
    s.anchor(100, 8, 108)
    s.waves(14, 70, 122, 134, rows=3, opacity=0.45)
    s.waves(132, 188, 122, 134, rows=3, opacity=0.45)
    s.birds([(30, 30), (46, 22), (38, 46)], 4)
    s.shadow(104, 121, 46)


DRAWINGS: dict[str, list[Callable[[Sketch], None]]] = {
    "hero-palace": [hero_palace_on_the_hill, hero_lighthouse, hero_observatory, hero_bridge, hero_island_in_the_clouds,
                    hero_palace_by_the_lake, hero_windmill_village, hero_tower_of_birds],
    "sidebar-tree": [sidebar_old_tree, sidebar_camp, sidebar_swing, sidebar_winter, sidebar_willow_and_bench, sidebar_well,
                     sidebar_reading_table],
    "heading-mountains": [heading_range, heading_windmills, heading_sea, heading_forest, heading_balloons, heading_village,
                          heading_river, heading_night_watch],
    "card-window": [card_pines, card_window, card_door, card_balloon, card_sailboat, card_shelf, card_stargazer, card_anchor],
    "margin-doodle": [doodle_spiral, doodle_stars, doodle_arrow, doodle_cube, doodle_flower, doodle_face, doodle_noughts_and_crosses,
                      doodle_paper_plane, doodle_lightbulb, doodle_scribble, doodle_cup, doodle_marks, doodle_eye, doodle_house,
                      doodle_loops, doodle_squares],
}


# --- app-icon: the shortcut on the desktop and in the application menu (256 x 256) ----------------------------

def app_icon(size: int) -> str:
    """A pencil brain on a paper tile. A desktop may be dark, so the drawing brings its own sheet of paper.

    Each pixel size gets its own drawing: below 48 px the fine folds and the shading would turn to grey mud,
    so a small icon keeps the outline and the two great furrows, drawn with a heavier hand."""
    s = Sketch("app-icon", seed=size * 7 + 3)
    hand = {16: 3.6, 24: 2.8, 32: 2.3, 48: 1.75, 64: 1.5, 128: 1.15}.get(size, 1.0)
    fine = size >= 48
    s.fills.append(f'<rect x="10" y="10" width="236" height="236" rx="46" fill="{PAPER}"/>')
    # The outline of the tile is a pencil line too, so the paper does not look cut by a machine.
    corner = [(10 + 46 - math.cos(step / 6 * math.pi / 2) * 46, 10 + 46 - math.sin(step / 6 * math.pi / 2) * 46) for step in range(7)]
    tile = [*corner, *[(246 - (x - 10), y) for x, y in reversed(corner)], *[(246 - (x - 10), 246 - (y - 10)) for x, y in corner],
            *[(x, 246 - (y - 10)) for x, y in reversed(corner)], corner[0]]
    s.line(tile, weight=1.6 * hand, opacity=0.5, shake=0.6, passes=1)
    brain(s, hand, fine)
    return s.svg().replace(f'width="256" height="256"', f'width="{size}" height="{size}"', 1)


def brand_mark() -> str:
    """The same brain beside the name in the sidebar, without its tile: the page is already paper.

    It is shown 40 px high, so it takes the small icon's drawing; the view box is cut to the brain itself."""
    s = Sketch("app-icon", seed=41)
    brain(s, 2.3, False)
    return s.svg().replace('viewBox="0 0 256 256" width="256" height="256"', 'viewBox="30 34 196 172" width="57" height="50"', 1)


def brain(s: Sketch, hand: float, fine: bool) -> None:
    # The cerebrum, facing left: a smooth contour pushed in and out along its length, which reads as gyri.
    outline = s.sample([(74, 162), (52, 144), (40, 114), (48, 84), (72, 60), (106, 46), (144, 44), (180, 52), (206, 72),
                        (218, 102), (212, 130), (192, 146), (168, 152), (146, 160), (116, 166), (90, 166), (74, 162)], steps=8)
    bumps = 13 if fine else 9
    shaped = []
    for index, (x, y) in enumerate(outline):
        angle = math.atan2(y - 108, x - 130)
        push = (3.6 if fine else 2.2) * math.sin(index / (len(outline) - 1) * math.tau * bumps)
        shaped.append((x + math.cos(angle) * push, y + math.sin(angle) * push))
    s.line(shaped, weight=3.0 * hand, opacity=0.9, shake=0.8)
    # The cerebellum tucked under the back, and the stem below it.
    s.flow([(170, 151), (176, 166), (192, 172), (206, 162), (210, 144), (204, 136)], weight=2.6 * hand, opacity=0.85, shake=0.6)
    s.flow([(146, 162), (148, 182), (151, 198)], weight=2.6 * hand, opacity=0.85, shake=0.5)
    s.flow([(166, 160), (167, 178), (170, 196)], weight=2.6 * hand, opacity=0.85, shake=0.5)
    # The two great furrows: the lateral one splits off the temporal lobe, the central one the frontal.
    s.flow([(84, 142), (110, 132), (138, 122), (160, 120), (180, 128)], weight=2.6 * hand, opacity=0.85, shake=0.6)
    s.flow([(138, 48), (132, 70), (140, 88), (132, 106), (136, 120)], weight=2.4 * hand, opacity=0.85, shake=0.6)
    if not fine:
        s.flow([(70, 104), (86, 96), (96, 108), (112, 98)], weight=2.0 * hand, opacity=0.75, shake=0.5)
        s.flow([(166, 70), (156, 88), (172, 98), (164, 112)], weight=2.0 * hand, opacity=0.75, shake=0.5)
    else:
        for fold in ([(60, 98), (74, 90), (84, 102), (100, 92), (108, 100)], [(68, 124), (82, 114), (96, 124), (112, 110)],
                     [(92, 68), (108, 78), (102, 92), (118, 100)], [(112, 60), (120, 66)], [(160, 64), (152, 82), (166, 92), (158, 108)],
                     [(184, 76), (196, 92), (184, 106), (200, 116)], [(148, 100), (166, 106), (178, 100)],
                     [(100, 152), (118, 144), (136, 150), (156, 140)], [(88, 156), (96, 150)]):
            s.flow(fold, weight=1.7 * hand, opacity=0.7, shake=0.6)
        for left, right, y in ((178, 204, 152), (180, 204, 160)):
            s.curve((left, y), (right, y - 4), -3, weight=1.2 * hand, opacity=0.6, shake=0.4, passes=1)
        # The shaded underside: hatching under the temporal lobe and the cerebellum.
        s.hatch(94, 152, 64, 12, count=12, lean=0.35, opacity=0.4)
        s.hatch(184, 158, 20, 12, count=5, lean=0.3, opacity=0.4)


def render() -> dict[str, str]:
    files: dict[str, str] = {}
    for slot, recipes in DRAWINGS.items():
        for index, recipe in enumerate(recipes, start=1):
            sketch = Sketch(slot, seed=index * 101 + len(slot))
            recipe(sketch)
            files[f"{slot}-{index:02}.svg"] = sketch.svg()
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "beyin_web" / "static" / "img")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    files = render()
    for name, text in files.items():
        (args.out / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(files)} drawings, {sum(len(text.encode('utf-8')) for text in files.values()) // 1024} KB -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
