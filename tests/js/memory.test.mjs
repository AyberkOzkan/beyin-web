import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { scopeList, filterRules, indicatorState, memorySize, warningsPreview, sectionFromHash,
  sectionHasContent, warningCodes } from "../../beyin_web/static/js/pages/memory-model.js";

const golden = name => JSON.parse(readFileSync(new URL(`../fixtures/golden/${name}.json`, import.meta.url), "utf8"));
const memory = golden("memory");
const health = golden("health");
const messages = JSON.parse(readFileSync(new URL("../../beyin_web/static/i18n/tr.json", import.meta.url), "utf8"));

test("scope list omits empty scopes, sorts unique values and filters exact matches", () => {
  const items = memory.rules.items;
  assert.deepEqual(scopeList(items), ["atlas", "genel"]);
  assert.deepEqual(scopeList([...items, items[0]]), ["atlas", "genel"]);
  assert.deepEqual(filterRules(items, "atlas"), [items[0]]);
  assert.deepEqual(filterRules(items, "genel"), [items[1]]);
  assert.deepEqual(filterRules(items), items);
  assert.deepEqual(filterRules(items, "missing"), []);
  assert.deepEqual(scopeList(), []);
  assert.deepEqual(filterRules(), []);
});

test("pulse indicator selects green, amber and gray with translated accessible names", () => {
  assert.deepEqual(indicatorState(golden("pulse")), { tone: "active", key: "health.indicator.current" });
  for (const up_to_date of [false, null, undefined]) {
    assert.deepEqual(indicatorState({ beyin: { available: true, up_to_date } }),
      { tone: "waiting", key: "health.indicator.outdated" });
  }
  for (const pulse of [undefined, {}, { beyin: { available: false, up_to_date: true } }]) {
    assert.deepEqual(indicatorState(pulse), { tone: "unknown", key: "health.indicator.plain" });
  }
  for (const state of ["current", "outdated", "plain"]) assert.ok(messages[`health.indicator.${state}`]);
});

test("memory size preserves character counts and caps the limit ratio", () => {
  assert.deepEqual(memorySize(health.health_summary.memory_files["Last-Session.md"]),
    { chars: 120, limit: 1200, ratio: 0.1, overLimit: false });
  assert.deepEqual(memorySize(health.health_summary.memory_files["Core.md"]),
    { chars: 90, limit: null, ratio: null, overLimit: false });
  assert.deepEqual(memorySize({ chars: 150, limit: 100 }), { chars: 150, limit: 100, ratio: 1, overLimit: true });
  assert.deepEqual(memorySize({ chars: 100, limit: 100 }), { chars: 100, limit: 100, ratio: 1, overLimit: false });
  assert.equal(memorySize({ chars: 0, limit: 100 }).ratio, 0);
  assert.equal(memorySize({ chars: 1, limit: 100, over_limit: true }).overLimit, true);
  for (const limit of [null, 0, -1, Infinity, NaN]) assert.equal(memorySize({ chars: 10, limit }).ratio, null);
  for (const chars of [null, -1, Infinity, NaN]) assert.equal(memorySize({ chars }).chars, 0);
});

test("warnings show the first ten, retain order and count only the remainder", () => {
  assert.deepEqual(warningsPreview(), { visible: [], remaining: 0 });
  assert.deepEqual(warningsPreview(health.warnings), { visible: health.warnings, remaining: 0 });
  const warnings = Array.from({ length: 13 }, (_, index) => ({ code: `unknown_${index}`, path: null }));
  assert.deepEqual(warningsPreview(warnings), { visible: warnings.slice(0, 10), remaining: 3 });
  assert.equal(warningsPreview(warnings.slice(0, 10)).remaining, 0);
  assert.equal(warnings.length, 13);
  assert.equal(warningCodes.has("unknown_0"), false);
  for (const code of warningCodes) assert.ok(messages[`health.warning.${code}`]);
});

test("section comes from bolum, rejects unknown names and ignores unrelated query values", () => {
  for (const section of ["kimlik", "kurallar", "oturum", "konular"]) {
    assert.equal(sectionFromHash(`#/hafiza?kapsam=atlas&bolum=${section}`), section);
  }
  assert.equal(sectionFromHash("#/hafiza?bolum=%6Boturum"), "kimlik");
  assert.equal(sectionFromHash("#/hafiza?bolum=%6Bonular"), "konular");
  for (const hash of [undefined, "#/hafiza", "#/hafiza?bolum=missing", "#/hafiza?bolum="]) {
    assert.equal(sectionFromHash(hash), "kimlik");
  }
});

test("section content distinguishes Markdown fallbacks from empty memory", () => {
  for (const name of ["identity", "rules", "last_session", "threads"]) {
    assert.equal(sectionHasContent(memory[name], name), true);
    assert.equal(sectionHasContent({ structured: false, raw: " \n" }, name), false);
    assert.equal(sectionHasContent({ structured: false, raw: "# Free form" }, name), true);
    assert.equal(sectionHasContent(undefined, name), false);
  }
  assert.equal(sectionHasContent({ structured: false, raw: "", records: [{ body: "Identity" }] }, "identity"), true);
  assert.equal(sectionHasContent({ structured: true, active: [], closed: [{}] }, "threads"), true);
  assert.equal(sectionHasContent({ structured: true, items: [] }, "rules"), false);
});
