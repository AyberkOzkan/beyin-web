import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { readSearchState, searchHash, searchApiParams, highlightParts, debounce,
  requestGate, commitSearchHistory, searchKinds } from "../../beyin_web/static/js/pages/search-model.js";
import { render, destroy, handlesChanges } from "../../beyin_web/static/js/pages/search.js";

test("search module exposes the page contract", () => {
  assert.equal(typeof render, "function");
  assert.equal(typeof destroy, "function");
  assert.equal(handlesChanges, true);
});

test("search addresses round trip and omit defaults and unknown modes and kinds", () => {
  const defaults = { q: "", kip: "notlar", tur: "", proje: "" };
  assert.deepEqual(readSearchState("#/arama"), defaults);
  assert.equal(searchHash(defaults), "#/arama");
  assert.equal(searchHash({ q: "  ", kip: "notlar", tur: "unknown" }), "#/arama");
  assert.deepEqual(readSearchState("#/arama?q=Atlas&kip=unknown&tur=unknown&other=ignored"), { ...defaults, q: "Atlas" });
  for (const kip of ["notlar", "beyin"]) {
    for (const tur of ["", ...searchKinds]) {
      const state = { q: "Çalışma & soru? # + 🧠", kip, tur, proje: "çınar / atlas" };
      assert.deepEqual(readSearchState(searchHash(state)), state);
      if (kip === "notlar") assert.doesNotMatch(searchHash(state), /kip=/);
      if (!tur) assert.doesNotMatch(searchHash(state), /tur=/);
    }
  }
  assert.equal(searchHash({ q: " Atlas ", page: "search" }), "#/arama?q=Atlas");
});

test("search state translates only the agreed API parameters", () => {
  assert.deepEqual(searchApiParams({ q: "Atlas" }), { q: "Atlas", mode: "local" });
  assert.deepEqual(searchApiParams({ q: "  soru  ", kip: "beyin", tur: "knowledge", proje: "atlas" }),
    { q: "soru", mode: "beyin", kind: "knowledge", project: "atlas" });
  assert.deepEqual(searchApiParams({ kip: "unknown", tur: "fact", proje: "", other: "ignored" }), { q: "", mode: "local" });
});

test("highlight parts merge overlapping and adjacent ranges, clamp bounds and preserve text", () => {
  assert.deepEqual(highlightParts("abcdefghij", [[4, 7], [1, 4], [2, 5], [8, 99], [-5, -1], [9, 8], [1, 1], [30, 40]]), [
    { text: "a", marked: false }, { text: "bcdefg", marked: true },
    { text: "h", marked: false }, { text: "ij", marked: true },
  ]);
  assert.deepEqual(highlightParts("abc", [[-2, 1], [1, 99]]), [{ text: "abc", marked: true }]);
  assert.deepEqual(highlightParts("<script>&çalışma", [[9, 16], null, [NaN, 3], [1.5, 3], ["0", 2]]), [
    { text: "<script>&", marked: false }, { text: "çalışma", marked: true },
  ]);
  assert.deepEqual(highlightParts("🧠 çalışma", [[2, 9]]), [{ text: "🧠 ", marked: false }, { text: "çalışma", marked: true }]);
  assert.deepEqual(highlightParts("abc"), [{ text: "abc", marked: false }]);
  assert.deepEqual(highlightParts("", [[0, 5]]), []);
  const golden = JSON.parse(readFileSync(new URL("../fixtures/golden/search.json", import.meta.url), "utf8"));
  for (const record of golden.results) {
    const parts = highlightParts(record.snippet, record.highlights);
    assert.equal(parts.map(part => part.text).join(""), record.snippet);
    assert.ok(parts.some(part => part.marked && part.text.toLocaleLowerCase("tr-TR") === "atlas"));
  }
});

test("debounce waits 250 ms after the last edit and supports immediate flush and cleanup", context => {
  context.mock.timers.enable({ apis: ["setTimeout"] });
  const values = [];
  const delayed = debounce(value => values.push(value));
  delayed("A");
  context.mock.timers.tick(200);
  delayed("Atlas");
  context.mock.timers.tick(249);
  assert.deepEqual(values, []);
  context.mock.timers.tick(1);
  assert.deepEqual(values, ["Atlas"]);
  delayed("next");
  delayed.flush();
  delayed.flush();
  context.mock.timers.tick(250);
  assert.deepEqual(values, ["Atlas", "next"]);
  delayed("destroyed");
  delayed.cancel();
  context.mock.timers.tick(1000);
  assert.deepEqual(values, ["Atlas", "next"]);
});

test("older responses and failures cannot replace a new request or an edited query", async () => {
  const gate = requestGate();
  const displayed = [];
  const pending = [];
  const request = () => {
    const current = gate.issue();
    return new Promise(resolve => pending.push(resolve)).then(value => { if (current()) displayed.push(value); });
  };
  const first = request();
  const second = request();
  pending[1]("new");
  await second;
  pending[0]("old");
  await first;
  assert.deepEqual(displayed, ["new"]);
  const third = request();
  gate.invalidate();
  pending[2]("arrived during debounce or after destroy");
  await third;
  assert.deepEqual(displayed, ["new"]);
  const oldFailure = gate.issue();
  gate.issue();
  assert.equal(oldFailure(), false);
});

test("Enter restores the prior committed query before adding the new preview to history", () => {
  const entries = ["#/arama?q=Atlas"];
  const history = {
    state: { preserved: true },
    replaceState(state, title, hash) { assert.equal(state, this.state); entries[entries.length - 1] = hash; },
    pushState(state, title, hash) { assert.equal(state, this.state); entries.push(hash); },
  };
  history.replaceState(history.state, "", "#/arama?q=next");
  commitSearchHistory(history, "#/arama?q=Atlas", "#/arama?q=next");
  assert.deepEqual(entries, ["#/arama?q=Atlas", "#/arama?q=next"]);
  history.replaceState(history.state, "", "#/arama?q=third");
  commitSearchHistory(history, "#/arama?q=next", "#/arama?q=third");
  assert.deepEqual(entries, ["#/arama?q=Atlas", "#/arama?q=next", "#/arama?q=third"]);
});
