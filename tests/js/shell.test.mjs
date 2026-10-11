import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseRoute } from "../../beyin_web/static/js/router.js";
import { setMessages, t, relativeTime, formatDate, formatTime } from "../../beyin_web/static/js/i18n.js";
import { resolveWikilink, renderMarkdown } from "../../beyin_web/static/js/markdown.js";

const messages = JSON.parse(readFileSync(new URL("../../beyin_web/static/i18n/tr.json", import.meta.url), "utf8"));
setMessages(messages);

test("every route in the contract parses with decoded parameters", () => {
  const cases = [
    ["", "home", {}], ["#/", "home", {}], ["#/projeler", "projects", {}],
    ["#/projeler/%C3%87%C4%B1nar", "projects", { name: "Çınar" }],
    ["#/bilgi", "knowledge", {}], ["#/not/df96cd83303a", "record", { rid: "df96cd83303a" }],
    ["#/gunlukler", "journal", {}], ["#/gunlukler/2026-01-12", "journal", { date: "2026-01-12" }],
    ["#/grafik?odak=abc", "graph", { odak: "abc" }], ["#/grafik", "graph", {}],
    ["#/arama?q=%C4%B1%C5%9F%C4%B1k+ve+bilgi", "search", { q: "ışık ve bilgi" }],
    ["#/hafiza", "memory", {}], ["#/_vitrin", "showcase", {}],
    ["#/missing", "notFound", {}], ["#/projeler/%XX", "notFound", {}],
  ];
  for (const [hash, page, params] of cases) assert.deepEqual(parseRoute(hash), { page, params });
  assert.deepEqual(parseRoute("#/projeler/atlas?name=other"), { page: "projects", params: { name: "atlas" } });
});

test("translation substitutes values as text, preserving missing variables", () => {
  assert.equal(t("shell.recordCount", { count: 30 }), "30 kayıt");
  assert.equal(t("component.progressValue", { current: 0, max: 5 }), "0 / 5");
  assert.equal(t("shell.recordCount", { count: "$&<script>" }), "$&<script> kayıt");
  assert.equal(t("shell.recordCount"), "{count} kayıt");
  const original = console.warn;
  const warnings = [];
  try {
    console.warn = message => warnings.push(message);
    assert.equal(t("unknown.key"), "unknown.key");
    assert.equal(warnings.length, 1);
  } finally { console.warn = original; }
});

test("relative times use Turkish with deterministic past and future dates", () => {
  const now = Date.parse("2026-01-12T12:00:00Z");
  assert.equal(relativeTime(now - 7200000, now), "2 saat önce");
  assert.equal(relativeTime(now + 120000, now), "2 dakika sonra");
  assert.equal(relativeTime(now - 86400000, now), "1 gün önce");
  assert.equal(relativeTime(now - 30000, now), "30 saniye önce");
  assert.match(formatDate(now), /12 Ocak 2026/);
  assert.match(formatTime(now), /^\d{2}:\d{2}$/);
});

test("wikilinks resolve targets, aliases, headings and private or unknown targets", () => {
  const links = { Atlas: "abc", "Çınar": "def" };
  assert.deepEqual(resolveWikilink("Atlas", links), { label: "Atlas", rid: "abc" });
  assert.deepEqual(resolveWikilink("Atlas|Ad", links), { label: "Ad", rid: "abc" });
  assert.deepEqual(resolveWikilink("Atlas#Amaç", links), { label: "Atlas#Amaç", rid: "abc" });
  assert.deepEqual(resolveWikilink("Çınar#Amaç|Ad", links), { label: "Ad", rid: "def" });
  assert.deepEqual(resolveWikilink("Gizli", links), { label: "Gizli", rid: null });
  assert.equal(resolveWikilink("constructor", links).rid, null);
});

test("Markdown escapes hostile HTML and attributes, blocks remote images and uses CSP-safe tables", () => {
  const html = renderMarkdown(messages["showcase.markdownBody"], { Atlas: "abc" });
  assert.doesNotMatch(html, /<script\b|<style\b|\sstyle=|<img\b/i);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /href="#\/not\/abc"/);
  assert.match(html, /<span class="wikilink-unresolved">Eksik not<\/span>/);
  assert.match(html, /class="align-center"/);
  assert.match(html, /class="align-right"/);
  assert.match(html, /type="checkbox" disabled>/);
  assert.match(html, /type="checkbox" disabled checked>/);
  assert.match(html, /target="_blank" rel="noopener noreferrer"/);
  assert.match(html, /<pre><code class="language-python">/);
  const hostile = renderMarkdown('[[Atlas|<img src=x onerror=alert(1)>]]\n\n[bad](javascript:alert(1))\n\n![remote](//example.org/x)', { Atlas: '" onclick="bad' });
  assert.doesNotMatch(hostile, /<img\b|href="javascript:|\sonclick=/);
  assert.match(hostile, /%22%20onclick%3D%22bad/);
});

test("code spans and fences keep literal wikilinks and checkbox markers", () => {
  const html = renderMarkdown("`[[Atlas]]`\n\n```\n[[Atlas]]\n- [x] task\n```", { Atlas: "abc" });
  assert.doesNotMatch(html, /class="wikilink"|type="checkbox"/);
  assert.match(html, /\[\[Atlas\]\]/);
  const nested = renderMarkdown("[ [[Atlas]] ](https://example.org)", { Atlas: "abc" });
  assert.equal((nested.match(/<a /g) || []).length, 1);
});
