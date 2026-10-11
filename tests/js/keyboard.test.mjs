import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { navigationIndex, shouldFocusMain, preserveFocus } from "../../beyin_web/static/js/accessibility.js";
import { headingLevels } from "../../beyin_web/static/js/markdown.js";
import { createSimulation, settleSimulation } from "../../beyin_web/static/js/components/graph-core.js";
import { createReader } from "../../beyin_web/static/js/components/reader.js";
import { tabs } from "../../beyin_web/static/js/components/index.js";
import { setMessages } from "../../beyin_web/static/js/i18n.js";

setMessages(JSON.parse(readFileSync(new URL("../../beyin_web/static/i18n/tr.json", import.meta.url), "utf8")));

test("navigation arrows wrap and Home and End select the endpoints", () => {
  assert.equal(navigationIndex("ArrowDown", 6, 7), 0);
  assert.equal(navigationIndex("ArrowUp", 0, 7), 6);
  assert.equal(navigationIndex("ArrowDown", 2, 7), 3);
  assert.equal(navigationIndex("ArrowUp", 2, 7), 1);
  assert.equal(navigationIndex("Home", 4, 7), 0);
  assert.equal(navigationIndex("End", 4, 7), 6);
  assert.equal(navigationIndex("Tab", 4, 7), -1);
  assert.equal(navigationIndex("End", 0, 0), -1);
});

test("focus moves only when changing page or addressed record", () => {
  const route = (page, params = {}) => ({ page, params });
  assert.equal(shouldFocusMain(undefined, route("home")), false);
  assert.equal(shouldFocusMain(route("home"), route("record", { rid: "a" })), true);
  assert.equal(shouldFocusMain(route("record", { rid: "a" }), route("record", { rid: "b" })), true);
  assert.equal(shouldFocusMain(route("record", { rid: "a" }), route("record", { rid: "a", q: "x" })), false);
  for (const page of ["projects", "knowledge", "journal", "graph", "search", "memory"]) {
    assert.equal(shouldFocusMain(route(page), route(page, { tab: "active", date: "2026-01-12", bolum: "kurallar" })), false);
  }
});

test("embedded note headings begin below section titles and cannot skip levels", () => {
  assert.deepEqual(headingLevels([1, 4, 6, 2, 1]), [3, 4, 5, 4, 3]);
  assert.deepEqual(headingLevels([3, 3, 6]), [3, 3, 4]);
  assert.deepEqual(headingLevels([]), []);
});

test("static graph layout settles before drawing and has a hard step limit", () => {
  let alpha = 1, ticks = 0, stopped = false;
  const simulation = {
    stop() { stopped = true; return this; },
    alpha(value) { if (value !== undefined) { alpha = value; return this; } return alpha; },
    alphaMin() { return 0.001; },
    tick() { ticks++; alpha *= 0.5; },
  };
  settleSimulation(simulation);
  assert.equal(stopped, true);
  assert.equal(ticks, 10);
  assert.equal(alpha, 0);
  simulation.tick = () => { ticks++; };
  ticks = 0; alpha = 1;
  settleSimulation(simulation, 12);
  assert.equal(ticks, 12);
  assert.equal(alpha, 0);
});

test("reduced-motion layouts place full and mini graph nodes without stacking", () => {
  const context = { setTimeout, clearTimeout, setInterval, clearInterval, performance };
  for (const name of ["d3-dispatch", "d3-quadtree", "d3-timer", "d3-force"]) {
    runInNewContext(readFileSync(new URL(`../../beyin_web/static/vendor/${name}.min.js`, import.meta.url), "utf8"), context);
  }
  const data = JSON.parse(readFileSync(new URL("../fixtures/golden/graph.json", import.meta.url), "utf8"));
  for (const options of [{ focus: data.nodes[0].id }, { center: true, collision: 82, distance: 190, charge: -650 }]) {
    const simulation = createSimulation(context.d3, data.nodes, data.edges, options).stop().alphaDecay(0.06);
    settleSimulation(simulation);
    assert.equal(simulation.alpha(), 0);
    const nodes = simulation.nodes();
    assert.ok(nodes.every(node => Number.isFinite(node.x) && Number.isFinite(node.y)));
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
      assert.ok(Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y) > 10);
    }
  }
});

// These component tests need event dispatch and element attributes, rather than a browser engine.
class TestNode extends EventTarget {
  constructor(tag = "#text", text = "") {
    super(); this.tagName = tag.toUpperCase(); this.textContent = text;
    this.children = []; this.attributes = new Map(); this.classList = { add() {} };
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  hasAttribute(name) { return this.attributes.has(name); }
  closest() { return null; }
  contains(node) { return node === this || this.children.some(child => child.contains(node)); }
  querySelectorAll(tag) { return this.children.flatMap(child => [...(child.tagName === tag ? [child] : []), ...child.querySelectorAll(tag)]); }
  get disabled() { return this.attributes.has("disabled"); }
  append(...nodes) { this.children.push(...nodes); }
  focus() { document.activeElement = this; }
  click() { this.dispatchEvent(new Event("click")); }
}

function withDom(run) {
  const originalNode = globalThis.Node, originalDocument = globalThis.document;
  globalThis.Node = TestNode;
  globalThis.document = Object.assign(new EventTarget(), {
    createElement: tag => new TestNode(tag), createElementNS: (_, tag) => new TestNode(tag),
    createTextNode: text => new TestNode("#text", text), activeElement: null,
    body: new TestNode("body"), documentElement: new TestNode("html"),
  });
  try { run(); }
  finally { globalThis.Node = originalNode; globalThis.document = originalDocument; }
}

const descendants = root => [root, ...root.children.flatMap(descendants)];

function withFocusObserver(run) {
  const originalObserver = globalThis.MutationObserver;
  let observer;
  globalThis.MutationObserver = class {
    constructor(callback) { observer = this; this.callback = callback; this.connected = false; }
    observe() { this.connected = true; }
    disconnect() { this.connected = false; }
    flush() { if (this.connected) this.callback(); }
  };
  try { withDom(() => run(() => observer)); }
  finally { globalThis.MutationObserver = originalObserver; }
}

function focusIn(target) {
  target.focus();
  const event = new Event("focusin");
  Object.defineProperty(event, "target", { value: target });
  document.dispatchEvent(event);
}

test("pending focus survives repeated renders and document fallback focus until an async control returns", () => withFocusObserver(getObserver => {
  const root = new TestNode("main"), original = new TestNode("select");
  original.setAttribute("id", "memory-scope");
  root.append(original);
  original.focus();
  const cancel = preserveFocus(root);
  const observer = getObserver();
  for (const fallback of [document.body, root, document.documentElement]) {
    root.children = [];
    focusIn(fallback);
    observer.flush();
    assert.equal(observer.connected, true);
  }
  const replacement = new TestNode("select");
  replacement.setAttribute("id", "memory-scope");
  root.append(replacement);
  observer.flush();
  assert.equal(document.activeElement, replacement);
  assert.equal(observer.connected, false);
  cancel();
}));

test("pending restoration cannot steal focus after the user chooses another control", () => withFocusObserver(getObserver => {
  const root = new TestNode("main"), original = new TestNode("select");
  original.setAttribute("id", "memory-scope");
  root.append(original);
  original.focus();
  const cancel = preserveFocus(root);
  const observer = getObserver();
  root.children = [];
  const other = new TestNode("button");
  focusIn(other);
  const replacement = new TestNode("select");
  replacement.setAttribute("id", "memory-scope");
  root.append(replacement);
  observer.flush();
  assert.equal(document.activeElement, other);
  assert.equal(observer.connected, false);
  cancel();
}));

test("reader omits absent or invalid Obsidian links and preserves a valid URI exactly", () => withDom(() => {
  const record = JSON.parse(readFileSync(new URL("../fixtures/golden/record.json", import.meta.url), "utf8"));
  for (const uri of [undefined, null, "", "https://example.org", "javascript:alert(1)", record.obsidian_uri]) {
    const input = { ...record, obsidian_uri: uri };
    if (uri === undefined) delete input.obsidian_uri;
    const reader = createReader(input);
    const links = descendants(reader.root).filter(node => node.tagName === "A" && node.getAttribute("href")?.startsWith("obsidian:"));
    assert.equal(links.length, uri === record.obsidian_uri ? 1 : 0);
    if (links.length) assert.equal(links[0].getAttribute("href"), uri);
    reader.destroy();
  }
}));

test("tabs keep roving focus, wrapping and disabled-tab exclusion", () => withDom(() => {
  const changes = [];
  const root = tabs([{ id: "all", label: "All" }, { id: "disabled", label: "Disabled", disabled: true },
    { id: "active", label: "Active" }], "all", id => changes.push(id));
  const [first, disabled, last] = root.children;
  first.focus();
  const press = key => {
    const event = new Event("keydown", { cancelable: true });
    Object.defineProperty(event, "key", { value: key });
    root.dispatchEvent(event);
    assert.equal(event.defaultPrevented, true);
  };
  for (const [key, expected] of [["ArrowRight", last], ["ArrowRight", first], ["ArrowLeft", last], ["Home", first], ["End", last]]) {
    press(key);
    assert.equal(document.activeElement, expected);
    assert.equal(expected.getAttribute("aria-selected"), "true");
    assert.equal(expected.tabIndex, 0);
    assert.equal(disabled.getAttribute("aria-selected"), "false");
  }
  assert.deepEqual(changes, ["active", "all", "active", "all", "active"]);
}));
