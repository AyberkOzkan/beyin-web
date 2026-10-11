import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { groupNotes, filterGroups, firstNote, firstSentence, recordKind, receiptDate, withoutLeadingTitle } from "../../beyin_web/static/js/pages/knowledge-model.js";
import { kindColor, truncateTitle, worldToScreen, screenToWorld, findNode } from "../../beyin_web/static/js/components/graph-core.js";
import { createReader } from "../../beyin_web/static/js/components/reader.js";
import { setMessages } from "../../beyin_web/static/js/i18n.js";

const golden = JSON.parse(readFileSync(new URL("../fixtures/golden/knowledge.json", import.meta.url), "utf8"));

test("reader announces its Obsidian target and clears it once when destroyed", () => {
  class ReaderNode extends EventTarget {
    constructor() { super(); this.children = []; this.classList = { add() {} }; }
    setAttribute() {}
    append(...nodes) { this.children.push(...nodes); }
  }
  const originalNode = globalThis.Node, originalDocument = globalThis.document;
  globalThis.Node = ReaderNode;
  globalThis.document = Object.assign(new EventTarget(), {
    createElement: () => new ReaderNode(), createElementNS: () => new ReaderNode(),
    createTextNode: () => new ReaderNode(),
  });
  try {
    setMessages(JSON.parse(readFileSync(new URL("../../beyin_web/static/i18n/tr.json", import.meta.url), "utf8")));
    const events = [];
    document.addEventListener("beyin:record", event => events.push(event.detail.obsidianUri));
    const record = JSON.parse(readFileSync(new URL("../fixtures/golden/record.json", import.meta.url), "utf8"));
    for (const uri of [record.obsidian_uri, undefined, "", "https://example.org"]) {
      const reader = createReader({ ...record, obsidian_uri: uri });
      assert.equal(events.at(-1), uri ?? "");
      reader.destroy();
      assert.equal(events.at(-1), null);
      const count = events.length;
      reader.destroy();
      assert.equal(events.length, count);
    }
  } finally { globalThis.Node = originalNode; globalThis.document = originalDocument; }
});

test("a body heading that repeats the title is dropped, any other heading stays", () => {
  assert.equal(withoutLeadingTitle("# Kavram bir\n\nMetin.", "Kavram bir"), "\nMetin.");
  assert.equal(withoutLeadingTitle("\n# Çınar Projesi #\r\nMetin.", "Çınar Projesi"), "Metin.");
  assert.equal(withoutLeadingTitle("# Başka başlık\n\nMetin.", "Kavram bir"), "# Başka başlık\n\nMetin.");
  assert.equal(withoutLeadingTitle("Metin.\n\n# Kavram bir", "Kavram bir"), "Metin.\n\n# Kavram bir");
  assert.equal(withoutLeadingTitle("## Kavram bir\n", "Kavram bir"), "## Kavram bir\n");
  assert.equal(withoutLeadingTitle(null, "x"), "");
});

test("knowledge groups preserve API order, including general notes", () => {
  const records = golden.groups.flatMap(group => group.records);
  assert.deepEqual(groupNotes(records), golden.groups);
  assert.deepEqual(firstNote(golden.groups), records[0]);
  assert.equal(firstNote([{ project: null, records: [] }, golden.groups[1]]).rid, records[1].rid);
  assert.equal(firstNote([]), null);
  assert.deepEqual(groupNotes([]), []);
});

test("knowledge filtering searches titles, summaries and projects with Turkish case rules", () => {
  const original = structuredClone(golden.groups);
  assert.equal(filterGroups(golden.groups, " temel ")[0].records[0].rid, golden.groups[1].records[0].rid);
  assert.equal(filterGroups(golden.groups, "ATLAS").length, 1);
  assert.equal(filterGroups(golden.groups, "projesiz")[0].project, null);
  assert.deepEqual(filterGroups(golden.groups, "absent"), []);
  assert.deepEqual(filterGroups(golden.groups, ""), golden.groups);
  assert.deepEqual(golden.groups, original);
  const groups = groupNotes([{ rid: "a", title: "İZ", summary: "IŞIK" }, { rid: "b", title: "İkinci" }]);
  assert.equal(filterGroups(groups, "ışık")[0].records[0].rid, "a");
  assert.equal(filterGroups(groups, "iz")[0].records[0].rid, "a");
});

test("receipt previews stop at a sentence or newline and preserve decimal values", () => {
  assert.equal(firstSentence(" **İlk** cümle. İkinci cümle! "), "İlk cümle.");
  assert.equal(firstSentence("3.14 değeridir! Devam."), "3.14 değeridir!");
  assert.equal(firstSentence("Bir satır\nİkinci satır"), "Bir satır");
  assert.equal(firstSentence("Son mu? Evet."), "Son mu?");
  assert.equal(firstSentence(null), "");
  assert.equal(firstSentence("Tek cümle"), "Tek cümle");
  assert.equal(receiptDate("2026-01-06T01:30:00+03:00"), "2026-01-06");
  assert.equal(recordKind("fact"), "knowledge");
  assert.equal(recordKind("untrusted"), "note");
});

test("graph kind colors use existing CSS tokens", () => {
  const mapping = { note: "--sage", fact: "--blue", knowledge: "--blue", task: "--amber",
    memory: "--sage-deep", receipt: "--ink-soft", unresolved: "--line", rejected: "--red" };
  for (const [kind, token] of Object.entries(mapping)) assert.equal(kindColor(kind), token);
  assert.equal(kindColor("new-kind"), "--ink-soft");
});

test("graph truncation counts Unicode code points and respects total length", () => {
  assert.equal(truncateTitle("Atlas", 5), "Atlas");
  assert.equal(truncateTitle("Atlas projesi", 6), "Atlas…");
  assert.equal(truncateTitle("🔮abc", 3), "🔮a…");
  assert.equal(truncateTitle("Atlas", 1), "…");
  assert.equal(truncateTitle("Atlas", 0), "");
  assert.equal(truncateTitle(null), "");
});

test("graph coordinates round trip through pan and zoom", () => {
  const point = { x: -17, y: 12 };
  const transform = { x: 120, y: -34, k: 2.5 };
  const screen = worldToScreen(point, transform);
  assert.deepEqual(screen, { x: 77.5, y: -4 });
  assert.deepEqual(screenToWorld(screen, transform), point);
  assert.deepEqual(worldToScreen(point), point);
  assert.deepEqual(screenToWorld(point), point);
});

test("graph hit testing picks the closest node inside its radius", () => {
  const nodes = [{ id: "a", x: 0, y: 0 }, { id: "b", x: 4, y: 0 }, { id: "c", x: 30, y: 0, radius: 2 }];
  assert.equal(findNode(nodes, { x: 3, y: 0 }, 5).id, "b");
  assert.equal(findNode(nodes, { x: -5, y: 0 }, 5).id, "a");
  assert.equal(findNode(nodes, { x: 33, y: 0 }, 5), null);
  assert.equal(findNode(nodes, { x: 100, y: 100 }), null);
  assert.equal(findNode([], { x: 0, y: 0 }), null);
});

test("P10 browser modules import without DOM work at module scope", async () => {
  for (const path of ["pages/knowledge.js", "pages/record.js", "components/reader.js", "components/context-panel.js", "components/mini-graph.js"]) {
    await import(`../../beyin_web/static/js/${path}`);
  }
});
