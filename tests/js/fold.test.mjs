import test from "node:test";
import assert from "node:assert/strict";
import { searchFold } from "../../beyin_web/static/js/fold.js";
import { searchMatches } from "../../beyin_web/static/js/pages/graph-model.js";
import { groupNotes, filterGroups } from "../../beyin_web/static/js/pages/knowledge-model.js";
import { filterRules } from "../../beyin_web/static/js/pages/memory-model.js";
import { filterProjects } from "../../beyin_web/static/js/pages/projects-model.js";

test("folding matches the server's search: Turkish letters and their plain forms are one", () => {
  // The expected values are those of search_fold in tests/test_search.py.
  assert.equal(searchFold("İ I ı Ç ç Ş ş Ğ ğ Ö ö Ü ü"), "i i i c c s s g g o o u u");
  assert.equal(searchFold("API"), "api");
  assert.equal(searchFold("IŞIK"), searchFold("ışık"));
  assert.equal(searchFold("İstanbul".normalize("NFD")), "istanbul");
  assert.equal(searchFold(null), "");
  assert.equal(searchFold(42), "42");
});

test("every page filter finds English words with a capital I and Turkish words typed without their dots", () => {
  const cases = [["api", "API notları"], ["install", "Install guide"], ["INDEX", "index"], ["cinar", "Çınar Projesi"],
    ["ÇINAR", "çınar"], ["isik", "IŞIK"], ["ışık", "ISIK"]];
  for (const [query, title] of cases) {
    const where = `${query} -> ${title}`;
    assert.equal(searchMatches([{ id: "a", title }, { id: "b", title: "Öteki" }], query).length, 1, where);
    assert.equal(filterGroups(groupNotes([{ rid: "a", title }, { rid: "b", title: "Öteki" }]), query)
      .flatMap(group => group.records).length, 1, where);
    assert.equal(filterRules([{ title, text: "" }, { title: "Öteki", text: "" }], "", query).length, 1, where);
    assert.equal(filterProjects([{ name: "a", title, summary: "" }, { name: "b", title: "Öteki", summary: "" }], query).length, 1, where);
  }
});
