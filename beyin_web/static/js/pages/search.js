import { get } from "../api.js";
import { el, icon } from "../dom.js";
import { t, formatDate, currentLocale } from "../i18n.js";
import { badge, tabs, emptyState, errorState, skeleton } from "../components/index.js";
import { preserveFocus } from "../accessibility.js";
import { searchKinds, readSearchState, searchHash, searchApiParams, highlightParts,
  debounce, requestGate, commitSearchHistory } from "./search-model.js";

const kindIcons = { note: "file-text", knowledge: "book-open", task: "list-todo", receipt: "scroll-text", memory: "brain" };
let active;

function listen(state, node, name, callback, capture = false) {
  node.addEventListener(name, callback, { signal: state.events.signal, capture });
}

function replaceAddress(state) {
  const hash = searchHash(state.query);
  if (location.hash === hash) return;
  state.replacements.push(new URL(hash, location.href).href);
  location.replace(hash);
}

function choose(state, changes = {}, commit = true) {
  if (active !== state) return;
  state.delayed.cancel();
  state.typing = false;
  state.query = readSearchState({ ...state.query, q: state.input.value, ...changes });
  if (state.available === false) state.query.kip = "notlar";
  if (commit) {
    const hash = searchHash(state.query);
    commitSearchHistory(history, state.committedHash, hash);
    state.committedHash = hash;
  } else replaceAddress(state);
  state.kind.value = state.query.tur;
  const project = state.project.querySelector("select");
  if (project) project.value = state.query.proje;
  state.clear.disabled = !state.input.value;
  updateDescription(state);
  void loadResults(state);
}

function updateDescription(state) {
  state.description.replaceChildren();
  if (state.query.kip === "beyin") state.description.append(el("p", { class: "search-explanation muted" }, t("search.beyinDescription")));
}

function resultCard(state, record, index) {
  const kind = record.kind === "fact" ? "knowledge" : kindIcons[record.kind] ? record.kind : "note";
  const heading = el("div", { class: "search-result-link" },
    icon(kindIcons[kind]), el("h2", {}, record.title));
  const link = el("a", { class: "search-result-body", href: `#/not/${encodeURIComponent(record.rid)}` }, heading);
  const content = el("p", { class: "search-snippet" });
  link.append(content);
  const card = el("article", { class: "card search-result", "data-rid": record.rid }, link);
  if (state.query.kip === "beyin") {
    content.textContent = record.text || "";
    content.id = `search-text-${index}`;
    if (Array.from(record.text || "").length > 600) {
      content.classList.add("search-collapsed");
      const more = el("button", { class: "button search-more", type: "button", "aria-expanded": "false",
        "aria-controls": content.id }, t("search.showMore"));
      listen(state, more, "click", () => {
        const collapsed = content.classList.toggle("search-collapsed");
        more.setAttribute("aria-expanded", String(!collapsed));
        more.textContent = t(collapsed ? "search.showMore" : "search.showLess");
      });
      card.append(more);
    }
  } else {
    for (const part of highlightParts(record.snippet || "", record.highlights || [])) {
      content.append(part.marked ? el("mark", {}, part.text) : document.createTextNode(part.text));
    }
  }
  const meta = el("div", { class: "search-result-meta row" }, el("span", { class: "search-path muted" }, record.path), badge(kind));
  if (record.project) meta.append(el("span", { class: "badge search-project-badge" }, record.project));
  if (record.mtime) meta.append(el("time", { datetime: record.mtime, class: "muted" }, formatDate(record.mtime)));
  link.append(meta);
  return card;
}

async function loadResults(state) {
  const current = state.resultsGate.issue();
  if (active !== state) return;
  state.results.setAttribute("aria-busy", "false");
  state.summary.replaceChildren();
  state.notices.replaceChildren();
  if (!state.query.q) {
    state.results.replaceChildren(emptyState(t("search.hintTitle"), t("search.hint")));
    return;
  }
  if (state.available === undefined) {
    state.results.setAttribute("aria-busy", "true");
    state.results.replaceChildren(skeleton(4));
    return;
  }
  state.results.setAttribute("aria-busy", "true");
  state.results.replaceChildren(skeleton(4));
  const started = performance.now();
  try {
    const data = await get("/api/v1/search", searchApiParams(state.query));
    if (active !== state || !current()) return;
    const seconds = new Intl.NumberFormat(currentLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      .format((performance.now() - started) / 1000);
    state.summary.textContent = t("search.summary", { count: data.results.length, seconds });
    if (state.query.kip === "beyin") {
      if (data.stale_count > 0) state.notices.append(el("p", { class: "search-warning row", role: "status" },
        icon("triangle-alert"), t("search.stale")));
      if (data.omitted > 0) state.notices.append(el("p", { class: "muted" }, t("search.omitted", { count: data.omitted })));
    }
    state.results.replaceChildren(...(data.results.length ? data.results.map((record, index) => resultCard(state, record, index)) :
      [emptyState(t("search.noResultsTitle"), t(state.available ? "search.noResults" : "search.noResultsLocal"))]));
  } catch (error) {
    if (active !== state || !current() || error.code === "unauthorized") return;
    const unavailable = state.query.kip === "beyin" && ["runtime_unavailable", "timeout"].includes(error.code);
    state.results.replaceChildren(errorState(t(unavailable ? "search.beyinUnavailable" : "search.error"), () => void loadResults(state)));
  } finally {
    if (active === state && current()) state.results.setAttribute("aria-busy", "false");
  }
}

async function loadPulse(state) {
  const current = state.pulseGate.issue();
  state.cancelModesFocus?.();
  state.cancelModesFocus = preserveFocus(state.modes);
  state.modes.replaceChildren(skeleton(1));
  try {
    const data = await get("/api/v1/pulse");
    if (active !== state || !current()) return;
    state.available = Boolean(data.beyin?.available);
    if (!state.available && state.query.kip === "beyin") {
      state.query.kip = "notlar";
      state.committedHash = searchHash({ ...readSearchState(state.committedHash), kip: "notlar" });
      replaceAddress(state);
    }
    state.modes.replaceChildren();
    if (state.available) state.modes.append(tabs([
      { id: "notlar", label: t("search.modeLocal") }, { id: "beyin", label: t("search.modeBeyin") },
    ], state.query.kip, kip => choose(state, { kip })));
    updateDescription(state);
    if (!state.typing) void loadResults(state);
  } catch (error) {
    if (active !== state || !current() || error.code === "unauthorized") return;
    state.modes.replaceChildren(errorState(t("search.pulseError"), () => void loadPulse(state)));
    if (state.available === undefined && state.query.q) {
      state.results.setAttribute("aria-busy", "false");
      state.results.replaceChildren(errorState(t("search.pulseError"), () => void loadPulse(state)));
    }
  }
}

async function loadProjects(state) {
  const current = state.projectsGate.issue();
  state.cancelProjectFocus?.();
  state.cancelProjectFocus = preserveFocus(state.project);
  state.project.replaceChildren(skeleton(1));
  try {
    const data = await get("/api/v1/projects");
    if (active !== state || !current()) return;
    const select = el("select", { id: "search-project" }, el("option", { value: "" }, t("search.allProjects")),
      data.projects.map(project => el("option", { value: project.name }, project.title || project.name)));
    // Keep an addressed project visible even if its last note was removed.
    if (state.query.proje && !data.projects.some(project => project.name === state.query.proje)) {
      select.append(el("option", { value: state.query.proje }, state.query.proje));
    }
    select.value = state.query.proje;
    listen(state, select, "change", () => choose(state, { proje: select.value }));
    state.project.replaceChildren(el("label", { for: select.id }, t("search.project")), select);
    if (!data.projects.length) state.project.append(el("small", { class: "muted" }, t("search.projectsEmpty")));
  } catch (error) {
    if (active === state && current() && error.code !== "unauthorized") {
      state.project.replaceChildren(errorState(t("search.projectsError"), () => void loadProjects(state)));
    }
  }
}

export const handlesChanges = true;

export function render(root, params = {}) {
  destroy();
  const state = { query: readSearchState(params), available: undefined, events: new AbortController(),
    resultsGate: requestGate(), pulseGate: requestGate(), projectsGate: requestGate(), replacements: [], typing: false };
  active = state;
  state.committedHash = searchHash(state.query);
  state.root = el("div", { class: "search-page stack" });
  state.input = el("input", { id: "search-query", type: "search", value: state.query.q, autocomplete: "off",
    "aria-label": t("search.inputLabel"), placeholder: t("search.placeholder") });
  state.clear = el("button", { class: "icon-button", type: "button", disabled: !state.query.q,
    "aria-label": t("search.clear") }, icon("x"));
  const form = el("form", { class: "search-form" }, icon("search"), state.input, state.clear,
    el("button", { class: "button search-submit", type: "submit" }, t("search.submit")));
  state.modes = el("div", { class: "search-modes" }, skeleton(1));
  state.kind = el("select", { id: "search-kind" }, el("option", { value: "" }, t("search.allKinds")),
    searchKinds.map(kind => el("option", { value: kind }, t(`search.kind.${kind}`))));
  state.kind.value = state.query.tur;
  state.project = el("div", { class: "search-project-filter" }, skeleton(1));
  state.description = el("div", {});
  state.summary = el("p", { class: "search-summary muted", role: "status" });
  state.notices = el("div", { class: "search-notices", "aria-live": "polite" });
  state.results = el("section", { class: "search-results stack", "aria-label": t("search.results"), "aria-busy": "true" }, skeleton(4));
  state.root.append(el("header", {}, el("h1", {}, t("page.search.title")), el("p", { class: "muted" }, t("search.subtitle"))),
    form, state.modes, el("div", { class: "search-filters row" },
      el("div", { class: "search-kind-filter" }, el("label", { for: state.kind.id }, t("search.kind")), state.kind), state.project),
    state.description, state.summary, state.notices, state.results);
  root.replaceChildren(state.root);
  state.delayed = debounce(() => choose(state, {}, false));
  listen(state, state.input, "input", () => {
    state.typing = true;
    state.clear.disabled = !state.input.value;
    state.resultsGate.invalidate();
    state.delayed();
  });
  listen(state, form, "submit", event => { event.preventDefault(); choose(state); });
  listen(state, state.clear, "click", () => { state.input.value = ""; choose(state); state.input.focus(); });
  listen(state, state.kind, "change", () => choose(state, { tur: state.kind.value }));
  // Consume only our replacement events so the shell does not rebuild the focused form.
  listen(state, window, "hashchange", event => {
    const index = state.replacements.indexOf(event.newURL);
    if (index < 0) return;
    state.replacements.splice(index, 1);
    event.stopImmediatePropagation();
  }, true);
  listen(state, document, "beyin:changed", () => { void loadPulse(state); void loadProjects(state); });
  replaceAddress(state);
  state.input.focus();
  void loadResults(state);
  void loadPulse(state);
  void loadProjects(state);
}

export function destroy() {
  if (!active) return;
  active.cancelModesFocus?.();
  active.cancelProjectFocus?.();
  active.events.abort();
  active.delayed.cancel();
  active.resultsGate.invalidate();
  active.pulseGate.invalidate();
  active.projectsGate.invalidate();
  active.root.replaceChildren();
  active = null;
}
