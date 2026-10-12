import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setMessages } from "../../beyin_web/static/js/i18n.js";
import { shiftWeek, weekNavigation, rangeLabel, dailyPoints, percentage, activeDaysLabel } from "../../beyin_web/static/js/pages/reports-model.js";
import { render, destroy } from "../../beyin_web/static/js/pages/reports.js";

setMessages(JSON.parse(readFileSync(new URL("../../beyin_web/static/i18n/tr.json", import.meta.url), "utf8")));

test("report weeks normalize any day, cross years and stop at the server's current week", () => {
  assert.equal(shiftWeek("2026-01-07", -1), "2025-12-29");
  assert.equal(shiftWeek("2026-01-07", 1), "2026-01-12");
  assert.equal(shiftWeek("2025-12-31", 1), "2026-01-05");
  assert.equal(shiftWeek("2026-01-12", -1), "2026-01-05");
  assert.deepEqual(weekNavigation("2026-01-05", "2026-01-12"),
    { previous: "2025-12-29", next: "2026-01-12", current: "2026-01-12", isCurrent: false });
  assert.equal(weekNavigation("2026-01-12", "2026-01-18").next, null);
  assert.equal(weekNavigation("2026-01-12", "2026-01-18").isCurrent, true);
});

test("report range labels abbreviate only a shared month and year", () => {
  assert.equal(rangeLabel("2026-01-05", "2026-01-11"), "5–11 Ocak 2026");
  assert.equal(rangeLabel("2026-01-26", "2026-02-01"), "26 Ocak 2026 – 1 Şubat 2026");
  assert.equal(rangeLabel("2025-12-29", "2026-01-04"), "29 Aralık 2025 – 4 Ocak 2026");
});

test("30 day points include every zero, sort dates and scale a single peak", () => {
  const days = Object.fromEntries(Array.from({ length: 30 }, (_, index) => [`2026-01-${String(index + 1).padStart(2, "0")}`, 0]));
  assert.deepEqual(dailyPoints(days), []);
  assert.deepEqual(dailyPoints({}), []);
  days["2026-01-16"] = 5;
  const points = dailyPoints(Object.fromEntries(Object.entries(days).reverse()), 290, 100);
  assert.equal(points.length, 30);
  assert.deepEqual(points[0], { date: "2026-01-01", count: 0, x: 0, y: 100 });
  assert.deepEqual(points[15], { date: "2026-01-16", count: 5, x: 150, y: 0 });
  assert.deepEqual(points[29], { date: "2026-01-30", count: 0, x: 290, y: 100 });
  assert.ok(points.every(point => Number.isFinite(point.x) && Number.isFinite(point.y)));
  assert.deepEqual(dailyPoints({ "2026-01-01": 2 }, 100, 80), [{ date: "2026-01-01", count: 2, x: 50, y: 0 }]);
});

test("report progress and active day labels handle empty and bounded values", () => {
  assert.equal(percentage(1, 3), 33);
  assert.equal(percentage(0, 0), 0);
  assert.equal(percentage(5, 3), 100);
  assert.equal(percentage(-1, 3), 0);
  assert.equal(activeDaysLabel(3, 7), "3 / 7");
  assert.equal(activeDaysLabel(0, 30), "0 / 30");
  assert.equal(typeof render, "function");
  assert.equal(typeof destroy, "function");
});

test("destroy removes click handlers and late success or failure cannot touch the page", async () => {
  let mutations = 0, listeners = 0;
  class TestNode extends EventTarget {
    constructor() { super(); this.children = []; }
    setAttribute() { mutations++; }
    append(...children) { this.children.push(...children); mutations++; }
    replaceChildren(...children) { this.children = children; mutations++; }
    addEventListener(...args) { super.addEventListener(...args); listeners++; }
    removeEventListener(...args) { super.removeEventListener(...args); listeners--; }
  }
  const original = { Node: globalThis.Node, document: globalThis.document, fetch: globalThis.fetch };
  globalThis.Node = TestNode;
  globalThis.document = { createElement: () => new TestNode(), createElementNS: () => new TestNode(), createTextNode: () => new TestNode() };
  try {
    for (const failure of [false, true]) {
      let finish;
      const completed = new Promise(resolve => { finish = resolve; });
      globalThis.fetch = () => completed;
      render(new TestNode(), { hafta: failure ? "2026-01-06" : "2026-01-07" });
      assert.equal(listeners, 1);
      destroy();
      assert.equal(listeners, 0);
      const count = mutations;
      finish(new Response(JSON.stringify(failure ? { error: { code: "http_error" } } : {}), { status: failure ? 500 : 200 }));
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(mutations, count);
    }
  } finally {
    destroy();
    Object.assign(globalThis, original);
  }
});
