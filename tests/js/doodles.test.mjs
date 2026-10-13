import test from "node:test";
import assert from "node:assert/strict";
import { placeDoodles, seeded } from "../../beyin_web/static/js/components/doodles-model.js";

const sources = Array.from({ length: 16 }, (_, index) => `/static/img/margin-doodle-${String(index + 1).padStart(2, "0")}.svg`);
const overlaps = (a, b) => a.x < b.x + b.size && b.x < a.x + a.size && a.y < b.y + b.size && b.y < a.y + a.size;

test("the same seed gives the same sequence and another seed another", () => {
  const first = seeded("page:foot"), again = seeded("page:foot"), other = seeded("page:column");
  const values = Array.from({ length: 6 }, () => first());
  assert.deepEqual(values, Array.from({ length: 6 }, () => again()));
  assert.notDeepEqual(values, Array.from({ length: 6 }, () => other()));
  assert.ok(values.every(value => value >= 0 && value < 1));
});

test("doodles stay inside their zone, apart from each other, and differ while there are drawings left", () => {
  const zones = [{ key: "foot", x: 300, y: 500, width: 1300, height: 260 }, { key: "column-0-0", x: 300, y: 900, width: 360, height: 1000 },
    { key: "column-0-1", x: 700, y: 900, width: 560, height: 420 }];
  for (const seed of ["1:knowledge", "2:projects", "3:memory", "77:journal"]) {
    const placed = placeDoodles(zones, sources, seed);
    assert.deepEqual(placed, placeDoodles(zones, sources, seed));
    assert.ok(placed.length >= 3 && placed.length <= 9, String(placed.length));
    assert.equal(new Set(placed.map(item => item.source)).size, placed.length);
    for (const item of placed) {
      assert.ok(item.size >= 56 && item.size <= 108);
      assert.ok(Math.abs(item.turn) <= 14);
      assert.ok(zones.some(zone => item.x >= zone.x && item.x + item.size <= zone.x + zone.width &&
        item.y >= zone.y && item.y + item.size <= zone.y + zone.height), JSON.stringify(item));
    }
    for (const [index, item] of placed.entries()) {
      for (const other of placed.slice(index + 1)) assert.equal(overlaps(item, other), false);
    }
  }
  assert.notDeepEqual(placeDoodles(zones, sources, "1:knowledge"), placeDoodles(zones, sources, "2:knowledge"));
});

test("a zone too small for a doodle, or a page without drawings, stays bare", () => {
  for (const zone of [{ key: "a", x: 0, y: 0, width: 1200, height: 100 }, { key: "b", x: 0, y: 0, width: 140, height: 600 },
    { key: "c", x: 0, y: 0, width: 1200, height: -40 }, { key: "d", x: 0, y: 0, width: 149, height: 119 }]) {
    assert.deepEqual(placeDoodles([zone], sources, "seed"), [], zone.key);
  }
  assert.deepEqual(placeDoodles([{ key: "foot", x: 0, y: 0, width: 1200, height: 400 }], [], "seed"), []);
  assert.equal(placeDoodles([{ key: "foot", x: 0, y: 0, width: 400, height: 200 }], sources.slice(0, 1), "seed").length, 1);
});
