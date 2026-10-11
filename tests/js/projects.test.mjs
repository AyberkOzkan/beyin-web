import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { splitNote, taskIcon, filterProjects, projectCounts, newestProject, projectHash, firstSentence } from "../../beyin_web/static/js/pages/projects-model.js";
import { parseRoute } from "../../beyin_web/static/js/router.js";

const golden = JSON.parse(readFileSync(new URL("../fixtures/golden/projects.json", import.meta.url), "utf8"));

test("contents split level-two headings and preserve the introduction and nested headings", () => {
  const note = splitNote("\uFEFF# Project\r\nIntro\r\n## First\r\nOne\r\n### Nested\r\nMore\r\n## Second ##\r\nTwo\r\n");
  assert.equal(note.intro, "# Project\nIntro");
  assert.deepEqual(note.sections, [
    { id: "projects-note-section-1", title: "First", body: "One\n### Nested\nMore" },
    { id: "projects-note-section-2", title: "Second", body: "Two\n" },
  ]);
  assert.deepEqual(splitNote("plain\n##no heading\n    ## indented code\n> ## quote").sections, []);
  assert.equal(splitNote("").intro, "");
  assert.deepEqual(splitNote("# Short\nText").sections, []);
  assert.equal(splitNote("## Same\nA\n## Same\nB").sections.length, 2);
});

test("contents ignore backtick and tilde fences, including shorter or mismatched closers", () => {
  const body = ["## One", "````markdown", "## Hidden", "```", "## Still hidden", "~~~~", "````", "## Two",
    "   ~~~text", "## Hidden tilde", "   ~~~~", "## Three", "```", "## Unclosed"].join("\n");
  const { sections } = splitNote(body);
  assert.deepEqual(sections.map(section => section.title), ["One", "Two", "Three"]);
  assert.ok(sections[0].body.includes("## Still hidden"));
  assert.ok(sections[1].body.includes("## Hidden tilde"));
  assert.ok(sections[2].body.includes("## Unclosed"));
  assert.equal(splitNote("## One\n```text\n## Hidden\n``` trailing text\n## Also hidden").sections.length, 1);
});

test("a long note contains five sections even with heading-like code between them", () => {
  const { sections } = splitNote(Array.from({ length: 5 }, (_, index) =>
    `## Part ${index + 1}\nBody ${index + 1}\n\n\x60\x60\x60text\n## Code heading\n\x60\x60\x60`).join("\n\n"));
  assert.equal(sections.length, 5);
  assert.deepEqual(sections.map(section => section.title), ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5"]);
  assert.ok(sections.every(section => section.body.includes("## Code heading")));
});

test("contents ignore headings inside list fences, blockquotes and indented code", () => {
  const body = ["## One", "", "- ```text", "  ## Hidden in a list fence", "  ```", "",
    "> ## Quoted heading", "", "    ## Indented code", "", "## Two", "Body"].join("\n");
  const { sections } = splitNote(body);
  assert.deepEqual(sections.map(section => section.title), ["One", "Two"]);
  assert.ok(sections[0].body.includes("## Hidden in a list fence"));
  assert.ok(sections[0].body.includes("## Indented code"));
});

test("every task state maps to its documented sprite symbol, with a safe unknown fallback", () => {
  const expected = { done: "circle-check", active: "circle-dot", waiting: "circle-pause", blocked: "circle-x",
    inbox: "circle", cancelled: "ban" };
  const vendor = readFileSync(new URL("../../beyin_web/static/vendor/lucide-sprite.svg", import.meta.url), "utf8");
  for (const [status, name] of Object.entries(expected)) {
    assert.equal(taskIcon(status), name);
    assert.ok(vendor.includes(`id="${name}"`));
  }
  for (const status of [null, undefined, "unknown", "new", "toString", "__proto__"]) {
    assert.equal(taskIcon(status), "circle-dashed");
  }
});

test("filters match names, titles and summaries with Turkish case and NFC normalization", () => {
  const projects = [...golden.projects, { name: "quiet", title: "İzmir", summary: "Old summary", quiet: true }];
  assert.deepEqual(filterProjects(projects, "ÇINAR").map(project => project.name), ["cinar"]);
  assert.deepEqual(filterProjects(projects, "C\u0327INAR").map(project => project.name), ["cinar"]);
  assert.deepEqual(filterProjects(projects, "İZMİR").map(project => project.name), ["quiet"]);
  assert.deepEqual(filterProjects(projects, "sentetik").map(project => project.name), ["atlas"]);
  assert.deepEqual(filterProjects(projects, "cinar").map(project => project.name), ["cinar"]);
  assert.deepEqual(filterProjects(projects, "  ", "active"), golden.projects);
  assert.deepEqual(filterProjects(projects, "İZMİR", "active"), []);
  assert.deepEqual(filterProjects(projects, "missing"), []);
  assert.deepEqual(projectCounts(projects), { all: 3, active: 2 });
  assert.deepEqual(projectCounts([]), { all: 0, active: 0 });
});

test("newest selection compares instants, handles empty data and never reorders the list", () => {
  const before = golden.projects.map(project => project.name);
  assert.equal(newestProject(golden.projects).name, "cinar");
  assert.deepEqual(golden.projects.map(project => project.name), before);
  assert.equal(newestProject([]), null);
  const earlier = { name: "a", last_activity: "2026-01-07T12:00:00+03:00" };
  const later = { name: "b", last_activity: "2026-01-07T10:00:00Z" };
  assert.equal(newestProject([earlier, later]), later);
  assert.equal(newestProject([{ name: "invalid", last_activity: "bad" }, earlier]), earlier);
  assert.equal(newestProject([earlier, { ...earlier, name: "tied" }]), earlier);
});

test("project URLs preserve query and tab state through the existing router", () => {
  assert.equal(projectHash(), "#/projeler");
  assert.equal(projectHash("atlas"), "#/projeler/atlas");
  const route = parseRoute(projectHash("İzmir / A", "Çınar & Atlas", "active"));
  assert.deepEqual(route, { page: "projects", params: { name: "İzmir / A", q: "Çınar & Atlas", tab: "active" } });
});

test("receipt previews show only the first sentence without losing decimals or punctuation", () => {
  for (const [input, expected] of [[null, ""], ["   ", ""], ["First. Second.", "First."],
    ["Ready? Continue.", "Ready?"], ["Done! Next.", "Done!"], ["3.11 works. More.", "3.11 works."],
    ["First\nSecond", "First"], ["**First** `step`.", "First step."]]) {
    assert.equal(firstSentence(input), expected);
  }
});

test("project translations are present for every data state and page action", () => {
  const messages = JSON.parse(readFileSync(new URL("../../beyin_web/static/i18n/tr.json", import.meta.url), "utf8"));
  for (const section of ["list", "project", "note", "tasks", "knowledge", "receipts"]) {
    for (const suffix of ["emptyTitle", "empty", "error"]) assert.equal(typeof messages[`projects.${section}.${suffix}`], "string");
  }
  for (const key of ["filter", "detail", "context", "lastActivity", "noActivity", "noTasks", "toc", "expandAll", "taskLabel",
    "tab.all", "tab.active", "tasks.title", "knowledge.title", "receipts.title"]) {
    assert.equal(typeof messages[`projects.${key}`], "string");
  }
});
