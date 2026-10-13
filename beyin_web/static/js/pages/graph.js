import { get } from "../api.js";
import { el } from "../dom.js";
import { t } from "../i18n.js";
import { headingArt, card, emptyState, errorState, filterBox, skeleton } from "../components/index.js";
import { createGraphCanvas } from "../components/graph-canvas.js";
import { layoutMetrics } from "../components/graph-core.js";
import { readState, stateHash, apiParams, adjacency, focusGraph, searchMatches } from "./graph-model.js";

let active;
const kinds = ["note", "fact", "task", "memory", "receipt"];
const kindName = kind => t(`graph.kind.${kinds.includes(kind) ? kind : kind === "knowledge" ? "fact" : "note"}`);

export function render(root, params = {}) {
  destroy();
  const state = readState(params);
  const session = { destroyed: false, controller: new AbortController(), graph: null, version: 0, selectionVersion: 0, limited: false };
  active = session;
  const listen = (target, name, callback) => target.addEventListener(name, callback, { signal: session.controller.signal });
  const button = (label, callback, attributes = {}) => {
    const node = el("button", { type: "button", class: "button", ...attributes }, label);
    listen(node, "click", callback);
    return node;
  };
  const navigate = changes => { if (!session.destroyed) location.hash = stateHash({ ...state, ...changes }); };
  const area = el("section", { class: "graph-area", "aria-label": t("graph.canvas") });
  const panel = el("aside", { class: "graph-panel stack", "aria-label": t("graph.details") });
  const notice = el("p", { class: "graph-notice muted", role: "status", hidden: true });
  const back = button(t("graph.back"), () => navigate({ focus: "" }), { class: "button graph-back", hidden: !state.focus });
  const search = filterBox({ label: t("graph.search"), value: state.query });
  const searchField = search.querySelector("input");
  const searchStatus = el("small", { class: "graph-search-status muted", role: "status" });
  const kind = el("select", { id: "graph-kind", "aria-label": t("graph.type") },
    el("option", { value: "" }, t("graph.allTypes")), kinds.map(value => el("option", { value }, kindName(value))));
  if (state.kind && !kinds.includes(state.kind)) kind.append(el("option", { value: state.kind }, kindName(state.kind)));
  kind.value = state.kind;
  listen(kind, "change", () => navigate({ kind: kind.value }));
  const project = el("select", { id: "graph-project", "aria-label": t("graph.project") }, el("option", { value: "" }, t("graph.allProjects")));
  if (state.project) project.append(el("option", { value: state.project }, state.project));
  project.value = state.project;
  listen(project, "change", () => navigate({ project: project.value }));
  const checkbox = (id, key, checked, property) => {
    const input = el("input", { id, type: "checkbox", checked });
    listen(input, "change", () => navigate({ [property]: input.checked }));
    return el("label", { class: "graph-check" }, input, t(key));
  };
  const filters = el("div", { class: "graph-filters row" },
    el("div", { class: "graph-search stack" }, search, searchStatus),
    el("label", { class: "graph-select" }, el("span", {}, t("graph.type")), kind),
    el("label", { class: "graph-select" }, el("span", {}, t("graph.project")), project),
    checkbox("graph-connected", "graph.connected", state.connectedOnly, "connectedOnly"),
    checkbox("graph-receipts", "graph.receipts", state.receipts, "receipts"));
  root.replaceChildren(el("div", { class: "graph-page" },
    el("header", { class: "page-heading" }, el("h1", {}, t("page.graph.title")), el("p", {}, t("page.graph.description")), headingArt("graph")),
    filters, el("div", { class: "row" }, back, notice), el("div", { class: "graph-layout" }, area, panel)));
  let data = { nodes: [], edges: [] };

  function showTips() {
    panel.replaceChildren(card(t("graph.details"), [el("p", { class: "muted" }, t("graph.tips"))]));
  }

  function updateSearch() {
    session.graph?.setSearch(state.query);
    searchStatus.textContent = state.query.trim() ? t("graph.matches", { count: searchMatches(data.nodes, state.query).length }) : "";
  }
  listen(searchField, "input", () => {
    state.query = searchField.value;
    history.replaceState(null, "", stateHash(state));
    updateSearch();
  });
  listen(searchField, "keydown", event => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const node = searchMatches(data.nodes, state.query)[0];
    if (node) session.graph?.center(node.id);
  });

  function showSelection(node) {
    if (session.destroyed) return;
    const version = ++session.selectionVersion;
    if (!node) { showTips(); return; }
    const ids = adjacency(data.nodes, data.edges).get(node.id) || new Set();
    const linked = data.nodes.filter(item => ids.has(item.id));
    const summary = el("div", { class: "graph-summary" }, skeleton(2));
    const field = (name, value) => [el("dt", {}, t(`graph.${name}`)), el("dd", { "data-field": name }, value)];
    const title = el("h2", { class: "graph-selected-title" }, node.title);
    const typeField = el("dd", { "data-field": "type" }, kindName(node.kind));
    panel.replaceChildren(el("section", { class: "card graph-selection", "data-rid": node.id }, title,
      el("dl", { class: "graph-fields" }, el("dt", {}, t("graph.type")), typeField,
        field("project", node.project || t("graph.general")), field("connections", String(node.degree))),
      el("h3", {}, t("graph.summary")), summary,
      el("h3", {}, t("graph.neighbors")), linked.length ? el("ul", { class: "graph-neighbors" }, linked.map(item =>
        el("li", {}, button(item.title, () => session.graph?.center(item.id), { "data-rid": item.id })))) :
        el("p", { class: "muted" }, t("graph.noNeighbors")),
      el("div", { class: "row" }, el("a", { class: "button graph-open-note", href: `#/not/${encodeURIComponent(node.id)}` }, t("graph.openNote")),
        button(t("graph.focus"), () => navigate({ focus: node.id })))));
    async function loadSummary() {
      if (session.destroyed || version !== session.selectionVersion) return;
      summary.replaceChildren(skeleton(2));
      try {
        const record = await get(`/api/v1/records/${encodeURIComponent(node.id)}`);
        if (session.destroyed || version !== session.selectionVersion) return;
        summary.replaceChildren(el("p", { class: "muted" }, record.excerpt || t("graph.noSummary")));
      } catch (error) {
        if (!session.destroyed && version === session.selectionVersion && error.code !== "unauthorized") {
          summary.replaceChildren(errorState(t("graph.summaryError"), () => void loadSummary()));
        }
      }
    }
    void loadSummary();
  }

  async function loadProjects() {
    const slot = el("div", { class: "graph-project-state" }, skeleton(1));
    project.parentElement.append(slot);
    async function fetchProjects() {
      slot.replaceChildren(skeleton(1));
      try {
        const result = await get("/api/v1/projects");
        if (session.destroyed) return;
        const names = new Set(result.projects.map(item => item.name));
        if (state.project) names.add(state.project);
        project.replaceChildren(el("option", { value: "" }, t("graph.allProjects")),
          ...[...names].sort((a, b) => a.localeCompare(b, "tr")).map(name => el("option", { value: name }, name)));
        project.value = state.project;
        slot.replaceChildren();
      } catch (error) {
        if (!session.destroyed && error.code !== "unauthorized") slot.replaceChildren(errorState(t("graph.projectsError"), () => void fetchProjects()));
      }
    }
    await fetchProjects();
  }

  async function load() {
    const version = ++session.version;
    ++session.selectionVersion;
    session.graph?.destroy();
    session.graph = null;
    area.replaceChildren(skeleton(5));
    showTips();
    try {
      const [result, memory, receiptContext] = await Promise.all([
        get("/api/v1/graph", apiParams(state)),
        // Graph nodes carry the stored kind, so use the classification filter to identify memory.
        get("/api/v1/graph", { kinds: "memory", connected_only: "0" }),
        // The API focus walk follows wikilinks only; complete receipt neighborhoods from graph edges.
        state.focus && state.receipts ? get("/api/v1/graph", apiParams({ ...state, focus: "" })) : null,
      ]);
      if (session.destroyed || version !== session.version) return;
      data = receiptContext ? focusGraph(receiptContext, state.focus) : result;
      if (data.nodes.length > 1500) {
        session.limited = true;
        if (!state.focus) {
          state.focus = data.nodes.reduce((best, node) => node.degree > best.degree ? node : best).id;
          history.replaceState(null, "", stateHash(state));
          data = await get("/api/v1/graph", apiParams(state));
          if (session.destroyed || version !== session.version) return;
          if (state.receipts) data = focusGraph(result, state.focus);
        }
      }
      back.hidden = !state.focus;
      notice.hidden = !session.limited;
      notice.textContent = session.limited ? t("graph.largeGraph") : "";
      const memoryIds = new Set(memory.nodes.map(node => node.id));
      data = { ...data, nodes: data.nodes.map(node => ({ ...node, kind: memoryIds.has(node.id) ? "memory" :
        kinds.includes(node.kind) ? node.kind : "note" })) };
      if (!data.nodes.length) {
        area.replaceChildren(emptyState(t("graph.emptyTitle"), t("graph.emptyMessage")));
        updateSearch();
        return;
      }
      const graph = await createGraphCanvas(data, { focus: state.focus, onSelect: showSelection, onFocus: id => navigate({ focus: id }) });
      if (session.destroyed || version !== session.version) { graph.destroy(); return; }
      session.graph = graph;
      // An on-demand snapshot keeps test inspection local to this canvas and off the frame loop.
      listen(graph.canvas, "graph:inspect", event => {
        if (typeof event.detail?.respond !== "function") return;
        const nodes = graph.positions();
        event.detail.respond({ nodes, edges: data.edges, metrics: layoutMetrics(nodes, data.edges) });
      });
      area.replaceChildren(graph.root);
      updateSearch();
      if (state.focus && data.nodes.some(node => node.id === state.focus)) graph.select(state.focus);
    } catch (error) {
      if (!session.destroyed && version === session.version && error.code !== "unauthorized") {
        area.replaceChildren(errorState(t("graph.loadError"), () => void load()));
      }
    }
  }
  void loadProjects();
  void load();
}

export function destroy() {
  if (!active) return;
  active.destroyed = true;
  active.controller.abort();
  active.graph?.destroy();
  ++active.version;
  ++active.selectionVersion;
  active = null;
}
