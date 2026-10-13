export { screenToWorld, worldToScreen, truncateTitle } from "../components/graph-core.js";
import { searchFold } from "../fold.js";

export function readState(params = {}) {
  if (typeof params === "string") params = Object.fromEntries(new URLSearchParams(params.split("?")[1] || ""));
  return {
    focus: params.odak || "", kind: params.tur || "", project: params.proje || "",
    receipts: params.receipt === "1", connectedOnly: params.yalniz !== "0", query: params.q || "",
  };
}

export function stateHash(state) {
  const params = new URLSearchParams();
  if (state.focus) params.set("odak", state.focus);
  if (state.kind) params.set("tur", state.kind);
  if (state.project) params.set("proje", state.project);
  if (state.receipts) params.set("receipt", "1");
  if (!state.connectedOnly) params.set("yalniz", "0");
  if (state.query) params.set("q", state.query);
  return "#/grafik" + (params.size ? "?" + params.toString() : "");
}

export function apiParams(state) {
  const params = { receipts: state.receipts ? "1" : "0", connected_only: state.connectedOnly ? "1" : "0" };
  if (state.kind) params.kinds = state.kind;
  if (state.project) params.project = state.project;
  if (state.focus) { params.focus = state.focus; params.depth = "2"; }
  return params;
}

const endpoint = value => typeof value === "object" ? value.id : value;

export function adjacency(nodes, edges) {
  const result = new Map(nodes.map(node => [node.id, new Set()]));
  for (const edge of edges) {
    const source = endpoint(edge.source), target = endpoint(edge.target);
    if (source === target || !result.has(source) || !result.has(target)) continue;
    result.get(source).add(target);
    result.get(target).add(source);
  }
  return result;
}

export function focusDistances(focus, neighbors) {
  const distances = new Map();
  if (!neighbors.has(focus)) return distances;
  distances.set(focus, 0);
  let frontier = [focus];
  for (let depth = 1; frontier.length; depth++) {
    const next = [];
    for (const id of frontier) for (const neighbor of neighbors.get(id) || []) {
      if (!distances.has(neighbor)) { distances.set(neighbor, depth); next.push(neighbor); }
    }
    frontier = next;
  }
  return distances;
}

export function focusGraph(data, focus, depth = 2) {
  const distances = focusDistances(focus, adjacency(data.nodes, data.edges));
  const nodes = data.nodes.filter(node => distances.has(node.id) && distances.get(node.id) <= depth);
  const ids = new Set(nodes.map(node => node.id));
  return { ...data, nodes, edges: data.edges.filter(edge => ids.has(endpoint(edge.source)) && ids.has(endpoint(edge.target))) };
}

export function searchMatches(nodes, query) {
  const needle = searchFold(query.trim());
  return needle ? nodes.filter(node => searchFold(node.title).includes(needle)) : [];
}
