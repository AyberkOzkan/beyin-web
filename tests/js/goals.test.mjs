import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { shiftMonth, monthFromParam, monthDays, monthLabel, monthNavigation, goalsHash, groupGoals, goalMeta,
  splitSteps, habitCount, goalPayload } from "../../beyin_web/static/js/pages/goals-model.js";
import { parseRoute } from "../../beyin_web/static/js/router.js";

const messages = JSON.parse(readFileSync(new URL("../../beyin_web/static/i18n/tr.json", import.meta.url), "utf8"));

test("months shift across years and list their own days", () => {
  assert.equal(shiftMonth("2026-01", -1), "2025-12");
  assert.equal(shiftMonth("2025-12", 1), "2026-01");
  assert.equal(shiftMonth("2026-03", -1), "2026-02");
  assert.equal(monthDays("2026-02").length, 28);
  assert.equal(monthDays("2024-02").length, 29);
  assert.deepEqual(monthDays("2026-01").slice(0, 2), ["2026-01-01", "2026-01-02"]);
  assert.equal(monthDays("2026-01").at(-1), "2026-01-31");
  assert.equal(monthLabel("2026-01"), "Ocak 2026");
});

test("the month comes from the address but never from the future", () => {
  assert.equal(monthFromParam("2025-12", "2026-01-12"), "2025-12");
  assert.equal(monthFromParam("2026-01", "2026-01-12"), "2026-01");
  for (const value of [undefined, "", "2026-02", "2999-01", "2026-13", "2026-1", "2026-01-12", "ocak", 202601]) {
    assert.equal(monthFromParam(value, "2026-01-12"), "2026-01");
  }
  assert.deepEqual(monthNavigation("2026-01", "2026-01-12"), { previous: "2025-12", next: null });
  assert.deepEqual(monthNavigation("2025-11", "2026-01-12"), { previous: "2025-10", next: "2025-12" });
  assert.equal(goalsHash("2026-01", "2026-01-12"), "#/hedefler");
  assert.equal(goalsHash("2025-12", "2026-01-12"), "#/hedefler?ay=2025-12");
  assert.deepEqual(parseRoute("#/hedefler?ay=2025-12"), { page: "goals", params: { ay: "2025-12" } });
});

test("goals are grouped by horizon and described by period and area", () => {
  const goals = [{ rid: "a", horizon: "year", period: "2026", area: "Üretim" }, { rid: "b", horizon: "long", period: null, area: null },
    { rid: "c", horizon: "long", period: "2025–2030", area: null }, { rid: "d", horizon: "long", period: null, area: "Sağlık" }];
  assert.deepEqual(groupGoals(goals), { long: [goals[1], goals[2], goals[3]], year: [goals[0]] });
  assert.deepEqual(groupGoals(), { long: [], year: [] });
  assert.deepEqual(goals.map(goalMeta), ["2026 · Üretim", "", "2025–2030", "Sağlık"]);
});

test("steps are one per line, without list markers or empty lines", () => {
  assert.deepEqual(splitSteps("Birinci kitap\r\n\n  - İkinci kitap  \n* [ ] Üçüncü\n- [x] Dördüncü\n   \n"),
    ["Birinci kitap", "İkinci kitap", "Üçüncü", "Dördüncü"]);
  assert.deepEqual(splitSteps(""), []);
  assert.deepEqual(splitSteps(), []);
  assert.deepEqual(splitSteps("-eksi ile başlayan"), ["-eksi ile başlayan"]);
});

test("a goal payload carries only what was filled in", () => {
  assert.deepEqual(goalPayload("year", { title: "  Spor ", period: " ", area: "", steps: "" }),
    { title: "Spor", horizon: "year", steps: [] });
  assert.deepEqual(goalPayload("long", { title: "İş", period: " 2025–2030 ", area: " Üretim", steps: "Bir\nİki" }),
    { title: "İş", horizon: "long", steps: ["Bir", "İki"], period: "2025–2030", area: "Üretim" });
});

test("habit days are counted within the shown month", () => {
  const habit = { days: ["2025-12-31", "2026-01-03", "2026-01-09", "2026-02-01"] };
  assert.equal(habitCount(habit, "2026-01"), 2);
  assert.equal(habitCount(habit, "2026-03"), 0);
  assert.equal(habitCount({}, "2026-01"), 0);
});

test("every goals message the page asks for exists", () => {
  const source = readFileSync(new URL("../../beyin_web/static/js/pages/goals.js", import.meta.url), "utf8");
  const keys = [...source.matchAll(/t\("(goals\.[\w.]+)"/g)].map(match => match[1]);
  assert.ok(keys.length > 10);
  for (const key of keys) assert.equal(typeof messages[key], "string", key);
  for (const section of ["long", "year", "theme", "areas", "habits"]) assert.ok(messages[`goals.${section}.title`]);
  for (const section of ["long", "year", "areas", "habits"]) {
    assert.ok(messages[`goals.${section}.emptyTitle`] && messages[`goals.${section}.empty`]);
  }
  for (const section of ["long", "year", "habits"]) assert.ok(messages[`goals.${section}.add`]);
  for (const horizon of ["long", "year"]) assert.ok(messages[`goals.field.period.${horizon}`]);
  for (const key of ["previous", "next"]) assert.ok(messages[`goals.habits.${key}`]);
  for (const kind of ["goal", "habit"]) assert.ok(messages[`goals.trash.kind.${kind}`]);
  assert.ok(messages["goals.trash.title"]);
});
