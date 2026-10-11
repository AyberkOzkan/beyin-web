import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { readState, stateHash, apiParams, adjacency, focusDistances, focusGraph, searchMatches, screenToWorld, worldToScreen, truncateTitle } from "../../beyin_web/static/js/pages/graph-model.js";
import { createSimulation, findNode, projectColor } from "../../beyin_web/static/js/components/graph-core.js";
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

test("titles truncate by code point and canvas hit testing distinguishes boxes and low zoom dots", () => {
  assert.equal(truncateTitle("Uzun bir başlık", 7), "Uzun b…");
  assert.equal(truncateTitle("🔮İki", 3), "🔮İ…");
  assert.equal(truncateTitle("Atlas", 5), "Atlas");
  assert.equal(truncateTitle("Atlas", 0), "");
  const node = { id: "a", x: 0, y: 0, width: 148, height: 36 };
  assert.equal(findNode([node], { x: 70, y: 15 }, 10, true), node);
  assert.equal(findNode([node], { x: 70, y: 20 }, 10, true), null);
  assert.equal(findNode([node], { x: 70, y: 15 }, 10), null);
  assert.equal(findNode([node], { x: 7, y: 0 }, 10), node);
  assert.equal(projectColor("atlas"), projectColor("atlas"));
  assert.match(projectColor("Çınar"), /^--(sage-deep|blue|amber|red|ink-soft)$/);
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
