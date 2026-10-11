import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { readState, stateHash, apiParams, adjacency, focusDistances, focusGraph, searchMatches, screenToWorld, worldToScreen, truncateTitle } from "../../beyin_web/static/js/pages/graph-model.js";
import { createSimulation, createSkySimulation, settleSimulation, findNode, projectColor, nodeRadius,
  labelOpacity, displayRadius, alignToHorizontal, driftParameters, driftOffset, starField, layoutMetrics } from "../../beyin_web/static/js/components/graph-core.js";
import * as page from "../../beyin_web/static/js/pages/graph.js";
import { createGraphCanvas } from "../../beyin_web/static/js/components/graph-canvas.js";

const data = JSON.parse(readFileSync(new URL("../fixtures/golden/graph.json", import.meta.url), "utf8"));

test("graph page and canvas expose the expected entry points", () => {
  for (const entry of [page.render, page.destroy, createGraphCanvas]) assert.equal(typeof entry, "function");
});

test("graph address round trips defaults, focus and every filter with escaped values", () => {
  const defaults = readState();
  assert.equal(stateHash(defaults), "#/grafik");
  assert.deepEqual(readState("#/grafik"), defaults);
  const state = { focus: "abc123", kind: "fact", project: "Çınar & /?#", receipts: true, connectedOnly: false, query: "İki + bir" };
  assert.deepEqual(readState(stateHash(state)), state);
  assert.equal(readState({ yalniz: "1", receipt: "0" }).connectedOnly, true);
  assert.equal(readState({ receipt: "true" }).receipts, false);
  assert.deepEqual(readState({ odak: "abc123", tur: "fact", proje: "atlas", receipt: "1", yalniz: "0", q: "Atlas" }),
    { focus: "abc123", kind: "fact", project: "atlas", receipts: true, connectedOnly: false, query: "Atlas" });
});

test("graph state translates only API parameters and asks for two focus hops", () => {
  assert.deepEqual(apiParams(readState()), { receipts: "0", connected_only: "1" });
  assert.deepEqual(apiParams(readState({ odak: "abc", tur: "fact", proje: "atlas", receipt: "1", yalniz: "0", q: "ignored" })),
    { receipts: "1", connected_only: "0", focus: "abc", depth: "2", kinds: "fact", project: "atlas" });
});

test("neighbors include incoming and outgoing edges, deduplicate reciprocal edges and ignore unknown endpoints", () => {
  const original = structuredClone(data);
  const neighbors = adjacency(data.nodes, [...data.edges, { source: "missing", target: data.nodes[0].id },
    { source: data.nodes[0].id, target: data.nodes[0].id }]);
  const atlas = data.nodes.find(node => node.title === "Atlas");
  assert.equal(neighbors.get(atlas.id).size, 3);
  assert.deepEqual(new Set([...neighbors.get(atlas.id)].map(id => data.nodes.find(node => node.id === id).title)),
    new Set(["Kavram bir", "Kavram iki", "Atlas A2: İkinci aşamayı tamamla"]));
  const distances = focusDistances(atlas.id, neighbors);
  assert.equal(distances.get(atlas.id), 0);
  assert.equal(distances.get(data.nodes.find(node => node.title === "index").id), 2);
  assert.equal(focusDistances("absent", neighbors).size, 0);
  const mutated = adjacency([{ id: "a" }, { id: "b" }, { id: "c" }], [{ source: { id: "a" }, target: { id: "b" } }]);
  assert.deepEqual([...mutated.get("a")], ["b"]);
  assert.equal(mutated.get("c").size, 0);
  assert.deepEqual(data, original);
});

test("search highlights titles with Turkish case folding, whitespace and Unicode normalization", () => {
  assert.equal(searchMatches(data.nodes, " aTLAS ").length, 2);
  assert.equal(searchMatches(data.nodes, "olmayan").length, 0);
  assert.equal(searchMatches(data.nodes, "").length, 0);
  const nodes = [{ id: "a", title: "İZ ve IŞIK" }, { id: "b", title: "Çınar" }];
  for (const query of ["iz", "ışık", "İZ"]) assert.equal(searchMatches(nodes, query)[0].id, "a");
  assert.equal(searchMatches(nodes, "C\u0327ınar")[0].id, "b");
});

test("receipt focus includes source references and two hops but excludes farther nodes", () => {
  const graph = { generation: 7, nodes: ["receipt", "a", "b", "c", "isolated"].map(id => ({ id })), edges: [
    { source: "receipt", target: "a", type: "ref" }, { source: "a", target: "b", type: "link" },
    { source: "b", target: "c", type: "link" },
  ] };
  const original = structuredClone(graph);
  const focused = focusGraph(graph, "receipt");
  assert.deepEqual(focused.nodes.map(node => node.id), ["receipt", "a", "b"]);
  assert.equal(focused.edges.length, 2);
  assert.equal(focused.generation, 7);
  assert.deepEqual(focusGraph(graph, "absent").nodes, []);
  assert.deepEqual(graph, original);
});

test("screen and world transformations round trip panning and several zoom levels", () => {
  for (const k of [0.08, 0.5, 1, 3]) {
    const point = { x: -60, y: 180 }, transform = { x: 234, y: -93, k };
    const restored = screenToWorld(worldToScreen(point, transform), transform);
    assert.ok(Math.abs(restored.x - point.x) < 1e-9);
    assert.ok(Math.abs(restored.y - point.y) < 1e-9);
  }
});

test("titles truncate by code point and circle hit testing chooses the nearest node", () => {
  assert.equal(truncateTitle("Uzun bir başlık", 7), "Uzun b…");
  assert.equal(truncateTitle("🔮İki", 3), "🔮İ…");
  assert.equal(truncateTitle("Atlas", 5), "Atlas");
  assert.equal(truncateTitle("Atlas", 0), "");
  const node = { id: "a", x: 0, y: 0, radius: 10 };
  assert.equal(findNode([node], { x: 70, y: 15 }), null);
  assert.equal(findNode([node], { x: 10, y: 0 }), node);
  assert.equal(findNode([node], { x: 7, y: 0 }, 10), node);
  const closer = { id: "b", x: 6, y: 0, radius: 4 };
  assert.equal(findNode([node, closer], { x: 7, y: 0 }), closer);
  assert.equal(projectColor("atlas"), projectColor("atlas"));
  assert.match(projectColor("Çınar"), /^--(sage-deep|blue|amber|red|ink-soft)$/);
});

test("sky circles grow with degree and stop at sixteen screen pixels", () => {
  assert.equal(nodeRadius(), 4);
  assert.equal(nodeRadius(-2), 4);
  assert.equal(nodeRadius(1), 6);
  assert.equal(nodeRadius(9), 10);
  assert.equal(nodeRadius(36), 16);
  assert.equal(nodeRadius(10000), 16);
});

test("labels fade linearly between 0.5 and 0.8 and highlighted labels stay visible", () => {
  for (const scale of [0, 0.08, 0.49, 0.5]) assert.equal(labelOpacity(scale), 0);
  assert.ok(Math.abs(labelOpacity(0.65) - 0.5) < 1e-12);
  for (const scale of [0.8, 1, 1.2, 3]) assert.equal(labelOpacity(scale), 1);
  assert.equal(displayRadius(36, 1), 16);
  assert.equal(displayRadius(36, 4), 16);
  assert.equal(displayRadius(36, 0.25), 8);
  assert.ok(Math.abs(displayRadius(36, 0.01) - 6.4) < 1e-12);
  for (const scale of [0.08, 0.6, 0.8, 1, 3]) assert.equal(labelOpacity(scale, true), 1);
});

test("drift is deterministic, bounded, slow and distinct for each identity", () => {
  for (const id of ["atlas", "Çınar", "🔮", "000000000001"]) {
    const parameters = driftParameters(id);
    assert.ok(parameters.amplitude >= 5 && parameters.amplitude <= 8);
    for (const period of [parameters.periodX, parameters.periodY]) assert.ok(period >= 7 && period <= 13);
    assert.deepEqual(driftOffset(id, 4), driftOffset(id, 4));
    assert.deepEqual(driftOffset(id, 4), driftOffset(id, 4, parameters));
    assert.notDeepEqual(driftOffset(id, 0), driftOffset(id, 4));
    for (let time = 0; time < 60; time += 0.1) {
      const offset = driftOffset(id, time, parameters);
      assert.ok(Math.abs(offset.x) <= parameters.amplitude && Math.abs(offset.y) <= parameters.amplitude);
      assert.ok(Math.hypot(offset.x, offset.y) <= parameters.amplitude + 1e-12);
    }
  }
  assert.notDeepEqual(driftOffset("atlas", 2), driftOffset("other", 2));
});

test("the stationary star field repeats its seed with small faint points", () => {
  const stars = starField("sky", 90);
  assert.deepEqual(stars, starField("sky", 90));
  assert.notDeepEqual(stars, starField("another", 90));
  assert.equal(stars.length, 90);
  assert.deepEqual(starField("sky", 0), []);
  for (const star of stars) {
    assert.ok(star.x >= 0.02 && star.x <= 0.98 && star.y >= 0.02 && star.y <= 0.98);
    assert.ok(star.size >= 1 && star.size <= 1.5 && star.opacity >= 0.2 && star.opacity <= 0.55);
  }
});

test("layout metrics measure closest centers, even and odd medians, and a hub's leaf spread", () => {
  const nodes = [{ id: "hub", x: 0, y: 0 }, { id: "a", x: 0, y: 120 }, { id: "b", x: 0, y: -240 },
    { id: "c", x: 36, y: 120 }];
  const edges = [{ source: "hub", target: "a" }, { source: { id: "hub" }, target: { id: "b" } }];
  const original = structuredClone({ nodes, edges });
  assert.deepEqual(layoutMetrics(nodes, edges), { minimumDistance: 36, medianLinkDistance: 180,
    leafSpreads: [{ id: "hub", leaves: 2, ratio: 2 }] });
  assert.equal(layoutMetrics(nodes, [...edges, { source: "a", target: "b" }]).medianLinkDistance, 240);
  assert.deepEqual(layoutMetrics([], []), { minimumDistance: Infinity, medianLinkDistance: 0, leafSpreads: [] });
  assert.deepEqual(layoutMetrics(nodes, [...edges, { source: "missing", target: "a" }, { source: "a", target: "a" }]),
    layoutMetrics(nodes, edges));
  assert.deepEqual({ nodes, edges }, original);
});

function vendorD3() {
  const context = { setTimeout, clearTimeout, setInterval, clearInterval, performance };
  for (const name of ["d3-dispatch", "d3-quadtree", "d3-timer", "d3-force"]) {
    runInNewContext(readFileSync(new URL(`../../beyin_web/static/vendor/${name}.min.js`, import.meta.url), "utf8"), context);
  }
  return context.d3;
}

test("vendored d3 spaces the golden graph, sixty hub leaves, and five hundred nodes", () => {
  const d3 = vendorD3();
  const star = { nodes: Array.from({ length: 61 }, (_, i) => ({ id: String(i) })),
    edges: Array.from({ length: 60 }, (_, i) => ({ source: "0", target: String(i + 1) })) };
  const dense = { nodes: Array.from({ length: 500 }, (_, i) => ({ id: String(i) })),
    edges: Array.from({ length: 1697 }, (_, i) => ({ source: String(i % 500), target: String((i * 71 + 13) % 500) })) };
  for (const graph of [data, star, dense]) {
    const original = structuredClone(graph);
    const simulation = createSkySimulation(d3, graph.nodes, graph.edges);
    settleSimulation(simulation);
    assert.equal(simulation.alpha(), 0);
    const metrics = layoutMetrics(simulation.nodes(), graph.edges);
    assert.ok(metrics.minimumDistance >= 36, JSON.stringify(metrics));
    assert.ok(metrics.medianLinkDistance >= 120, JSON.stringify(metrics));
    for (const spread of metrics.leafSpreads) assert.ok(spread.ratio >= 1.5);
    assert.deepEqual(graph, original);
  }
});

test("disconnected components settle on separate islands and focus remains pinned", () => {
  const nodes = Array.from({ length: 24 }, (_, i) => ({ id: String(i) }));
  const edges = [];
  for (let i = 0; i < 24; i++) edges.push({ source: String(i), target: String(Math.floor(i / 8) * 8 + (i + 1) % 8) });
  const simulation = createSkySimulation(vendorD3(), nodes, edges, "0");
  settleSimulation(simulation);
  const positions = simulation.nodes();
  assert.equal(positions[0].x, 0);
  assert.equal(positions[0].y, 0);
  for (let i = 0; i < 2; i++) {
    const right = Math.max(...positions.slice(i * 8, i * 8 + 8).map(node => node.x));
    const left = Math.min(...positions.slice(i * 8 + 8, i * 8 + 16).map(node => node.x));
    assert.ok(left > right + 36);
  }
});

test("shared d3 simulation keeps API inputs intact, preserves mini defaults and settles the full graph", () => {
  const context = { setTimeout, clearTimeout, setInterval, clearInterval, performance };
  for (const name of ["d3-dispatch", "d3-quadtree", "d3-timer", "d3-force"]) {
    runInNewContext(readFileSync(new URL(`../../beyin_web/static/vendor/${name}.min.js`, import.meta.url), "utf8"), context);
  }
  const original = structuredClone(data);
  const mini = createSimulation(context.d3, data.nodes, data.edges).stop();
  assert.equal(mini.force("center"), undefined);
  const simulation = createSimulation(context.d3, data.nodes, data.edges,
    { focus: data.nodes[0].id, center: true, collision: 82, distance: 190, charge: -650 }).stop().alphaDecay(0.06);
  assert.equal(typeof simulation.force("center"), "function");
  simulation.tick(120);
  assert.ok(simulation.alpha() < simulation.alphaMin());
  assert.ok(simulation.nodes().every(node => Number.isFinite(node.x) && Number.isFinite(node.y)));
  assert.equal(simulation.nodes()[0].x, 0);
  assert.deepEqual(data, original);
});

test("alignment turns the longest axis of a layout to x and keeps every distance", () => {
  const diagonal = Array.from({ length: 9 }, (_, index) => ({ id: String(index), x: index * 30 + (index % 2) * 8, y: index * 30, vx: 1, vy: 0 }));
  const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const before = distance(diagonal[0], diagonal[8]);
  assert.notEqual(alignToHorizontal(diagonal, { full: true }), 0);
  const spanX = Math.max(...diagonal.map(node => node.x)) - Math.min(...diagonal.map(node => node.x));
  const spanY = Math.max(...diagonal.map(node => node.y)) - Math.min(...diagonal.map(node => node.y));
  assert.ok(spanX > 8 * spanY);
  assert.ok(Math.abs(distance(diagonal[0], diagonal[8]) - before) < 1e-9);
  assert.ok(Math.abs(Math.hypot(diagonal[0].vx, diagonal[0].vy) - 1) < 1e-9);
  assert.ok(Math.abs(alignToHorizontal(diagonal, { full: true })) < 1e-3);
  const pinned = [{ id: "focus", x: 0, y: 0 }, { id: "a", x: 0, y: 100 }, { id: "b", x: 5, y: 200 }];
  alignToHorizontal(pinned, { pivot: { x: 0, y: 0 }, full: true });
  assert.deepEqual([pinned[0].x, pinned[0].y], [0, 0]);
  assert.ok(Math.abs(pinned[2].y) < Math.abs(pinned[2].x));
  const disc = [{ id: "a", x: 1, y: 0 }, { id: "b", x: -1, y: 0 }, { id: "c", x: 0, y: 1 }, { id: "d", x: 0, y: -1 }];
  assert.equal(alignToHorizontal(disc), 0);
  assert.equal(alignToHorizontal([{ id: "a", x: 0, y: 0 }, { id: "b", x: 3, y: 9 }]), 0);
});
