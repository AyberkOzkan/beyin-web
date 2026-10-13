import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseRoute } from "../../beyin_web/static/js/router.js";
import { setMessages, t, relativeTime, formatDate, formatTime } from "../../beyin_web/static/js/i18n.js";
import { resolveWikilink, renderMarkdown } from "../../beyin_web/static/js/markdown.js";
import { obsidianTarget, illustrationSlot } from "../../beyin_web/static/js/components/index.js";

const messages = JSON.parse(readFileSync(new URL("../../beyin_web/static/i18n/tr.json", import.meta.url), "utf8"));
setMessages(messages);

test("Obsidian target changes from vault to record and back, rejecting missing or unsafe URIs", () => {
  const vault = "obsidian://open?path=%2Fvault", record = vault + "%2Fnote.md";
  assert.deepEqual(obsidianTarget(vault), { href: vault, labelKey: "shell.openVaultObsidian" });
  assert.deepEqual(obsidianTarget(vault, record), { href: record, labelKey: "shell.openRecordObsidian" });
  assert.deepEqual(obsidianTarget(undefined, record), { href: record, labelKey: "shell.openRecordObsidian" });
  assert.deepEqual(obsidianTarget(vault, null), obsidianTarget(vault));
  for (const uri of [undefined, null, "", "https://example.org", "javascript:alert(1)", 12, "obsidian://other?"]) {
    assert.equal(obsidianTarget(uri), null);
    if (uri !== null && uri !== undefined) assert.equal(obsidianTarget(vault, uri), null);
  }
  assert.equal(t("shell.openObsidian"), "Obsidian'da Aç");
  assert.equal(t("shell.openVaultObsidian"), "Vault'u Obsidian'da aç");
  assert.equal(t("shell.openRecordObsidian"), "Bu notu Obsidian'da aç");
});

test("illustration slots accept only the four English names and local sources", () => {
  const original = globalThis.document;
  globalThis.document = {
    createElement: tag => ({ tag, attributes: {}, setAttribute(key, value) { this.attributes[key] = value; }, addEventListener() {} }),
  };
  try {
    for (const name of ["hero-palace", "sidebar-tree", "heading-mountains", "card-window"]) {
      const src = "/static/img/" + name + ".png";
      assert.equal(illustrationSlot(name, { [name]: src }).attributes.src, src);
      for (const bad of ["https://example.org/a.png", src + "?x", src + "#x", "/static/img/other.png"]) {
        assert.equal(illustrationSlot(name, { [name]: bad }), null);
      }
      assert.equal(illustrationSlot(name, {}), null);
    }
    // A slot with several drawings shows one of them, and keeps it for that place until the page is loaded again.
    const many = ["/static/img/card-window-01.svg", "/static/img/card-window-02.svg", "/static/img/card-window-by-night.webp"];
    const offered = { "card-window": [...many, "https://example.org/card-window-03.svg", "/static/img/card-window-04.svg?x", 7] };
    const seen = new Set();
    for (let place = 0; place < 60; place++) {
      const first = illustrationSlot("card-window", offered, `place-${place}`).attributes.src;
      assert.ok(many.includes(first), first);
      assert.equal(illustrationSlot("card-window", offered, `place-${place}`).attributes.src, first);
      seen.add(first);
    }
    assert.equal(seen.size, many.length);
    assert.equal(illustrationSlot("card-window", { "card-window": ["/static/img/card-window_05.svg", "/static/img/card-windows.svg"] }), null);
    assert.equal(illustrationSlot("card-window", { "card-window": [] }), null);
    const legacy = ["hero-" + "saray", "yan-" + "agac", "baslik-" + "daglar", "kart-" + "cam"];
    for (const name of legacy) assert.equal(illustrationSlot(name, { [name]: "/static/img/" + name + ".png" }), null);
  } finally { globalThis.document = original; }
});

test("every route in the contract parses with decoded parameters", () => {
  const cases = [
    ["", "home", {}], ["#/", "home", {}], ["#/projeler", "projects", {}],
    ["#/projeler/%C3%87%C4%B1nar", "projects", { name: "Çınar" }],
    ["#/bilgi", "knowledge", {}], ["#/not/df96cd83303a", "record", { rid: "df96cd83303a" }],
    ["#/gunlukler", "journal", {}], ["#/gunlukler/2026-01-12", "journal", { date: "2026-01-12" }],
    ["#/grafik?odak=abc", "graph", { odak: "abc" }], ["#/grafik", "graph", {}],
    ["#/arama?q=%C4%B1%C5%9F%C4%B1k+ve+bilgi", "search", { q: "ışık ve bilgi" }],
    ["#/hafiza", "memory", {}], ["#/_vitrin", "showcase", {}],
    ["#/raporlar", "reports", {}], ["#/raporlar?hafta=2026-01-07", "reports", { hafta: "2026-01-07" }],
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
