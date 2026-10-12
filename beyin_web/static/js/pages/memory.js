import { get } from "../api.js";
import { el } from "../dom.js";
import { t, formatDate, formatTime } from "../i18n.js";
import { mountMarkdown } from "../markdown.js";
import { card, tabs, filterBox, emptyState, errorState, skeleton } from "../components/index.js";
import { withoutLeadingTitle } from "./knowledge-model.js";
import { sections, sectionFromHash, scopeList, filterRules, sectionHasContent, sectionCount } from "./memory-model.js";

const names = ["identity", "rules", "last_session", "threads"];
let active = null;
// The search text is not in the address: choosing a scope redraws the page and must not clear it.
let ruleQuery = "";

function markdown(body) {
  const root = el("div", { class: "memory-markdown" });
  mountMarkdown(root, body, {});
  return root;
}

function date(value) {
  return value ? el("time", { datetime: value, class: "muted" }, formatDate(`${value}T12:00:00`)) : null;
}

function field(label, value, highlighted = false) {
  return el("div", { class: highlighted ? "memory-field memory-next-step" : "memory-field" },
    el("strong", {}, label), el("p", {}, value));
}

function empty(name) {
  return emptyState(t(`memory.${name}.title`), t(`memory.${name}.empty`));
}

// A rule is one line until it is opened: with a dozen rules the list stays readable at a glance.
function ruleRow(item) {
  if (!item.date) return el("article", { class: "memory-rule memory-rule-plain" }, el("p", {}, item.text));
  return el("details", { class: "memory-rule" },
    el("summary", {}, el("h3", {}, item.title),
      item.scope && el("span", { class: "badge memory-scope" }, item.scope), date(item.date)),
    el("p", {}, item.text),
    item.reason && field(t("memory.reason"), item.reason),
    item.source && field(t("memory.source"), item.source));
}

function rules(data, state) {
  const options = scopeList(data.items);
  const scope = options.includes(state.params.kapsam) ? state.params.kapsam : "";
  const select = el("select", { id: "memory-scope", onchange: event => {
    const query = new URLSearchParams(location.hash.split("?")[1] || "");
    query.set("bolum", "kurallar");
    if (event.target.value) query.set("kapsam", event.target.value);
    else query.delete("kapsam");
    location.hash = `/hafiza?${query}`;
  } }, el("option", { value: "", selected: !scope }, t("memory.allScopes")),
  options.map(value => el("option", { value, selected: value === scope }, value)));
  const list = el("div", { class: "memory-rules" });
  const count = el("small", { class: "muted memory-rule-count", role: "status" });
  const toggle = el("button", { type: "button", class: "button memory-toggle", onclick: () => {
    const rows = [...list.querySelectorAll("details")];
    const open = rows.some(row => !row.open);
    rows.forEach(row => { row.open = open; });
    label();
  } });
  function label() {
    const rows = [...list.querySelectorAll("details")];
    toggle.hidden = !rows.length;
    toggle.textContent = t(rows.some(row => !row.open) ? "memory.expandAll" : "memory.collapseAll");
  }
  function show() {
    const shown = filterRules(data.items, scope, ruleQuery);
    count.textContent = t("memory.ruleCount", { shown: shown.length, total: data.items.length });
    list.replaceChildren(...(shown.length ? shown.map(ruleRow) :
      [emptyState(t("memory.noMatchTitle"), t("memory.noMatch"))]));
    list.querySelectorAll("details").forEach(row => row.addEventListener("toggle", label));
    label();
  }
  const search = filterBox({ label: t("memory.ruleSearch"), value: ruleQuery, onInput: value => { ruleQuery = value; show(); } });
  search.classList.add("memory-search");
  show();
  return [el("div", { class: "memory-tools" }, search,
    el("label", { class: "memory-filter", for: "memory-scope" }, t("memory.scopeFilter"), select), toggle), count, list];
}

function session(data) {
  const current = data.card;
  const nextLabel = t("memory.nextStep");
  const items = current.items || [];
  return el("article", { class: "card memory-session" },
    el("div", { class: "row memory-meta" }, date(current.date),
      current.time && el("time", { datetime: current.time }, formatTime(current.time)),
      current.label && el("span", { class: "badge" }, current.label)),
    current.session && field(t("memory.sessionId"), current.session),
    items.map(([label, value]) => field(label, value, label === nextLabel)),
    current.next_step && !items.some(([label]) => label === nextLabel) && field(nextLabel, current.next_step, true));
}

function threadCard(thread) {
  const structured = [thread.owner, thread.status, thread.status_date, thread.open, thread.next_step].some(Boolean) || thread.extra?.length;
  if (!structured) {
    // The raw block starts with the thread's own "### title" line; show it as the heading it is.
    const text = (thread.raw || "").replace(/^\s*#{1,6}[ \t]+.*(?:\r?\n|$)/, "").trim();
    return el("article", { class: "card memory-thread" }, thread.title && el("h3", {}, thread.title),
      el("p", { class: "memory-raw" }, text || thread.raw));
  }
  return el("article", { class: "card memory-thread" }, el("h3", {}, thread.title),
    thread.owner && field(t("memory.owner"), thread.owner),
    (thread.status || thread.status_date) && el("div", { class: "row memory-meta" },
      el("strong", {}, t("memory.status")), thread.status && el("span", { class: "badge" }, thread.status), date(thread.status_date)),
    thread.open && field(t("memory.open"), thread.open),
    thread.next_step && field(t("memory.nextStep"), thread.next_step, true),
    (thread.extra || []).map(([label, value]) => field(label, value)));
}

function threads(data) {
  return [el("div", { class: "stack memory-active-threads" },
    data.active.length ? data.active.map(threadCard) : empty("threads")),
  el("details", { class: "memory-closed" }, el("summary", {}, t("memory.closed", { count: data.closed.length })),
    el("div", { class: "stack" }, data.closed.length ? data.closed.map(threadCard) :
      emptyState(t("memory.closedTitle"), t("memory.closedEmpty"))))];
}

function content(name, data, state) {
  // The section card already carries the title; a file that opens with the same heading would repeat it.
  const untitled = body => withoutLeadingTitle(body, t(`memory.${name}.title`));
  if (name === "identity" && data.records?.some(record => record.body?.trim())) {
    const bodies = data.records.map(record => untitled(record.body)).filter(body => body.trim());
    return bodies.length ? bodies.map(markdown) : [empty(name)];
  }
  if (data.structured === false) return untitled(data.raw).trim() ? [markdown(untitled(data.raw))] : [empty(name)];
  if (!sectionHasContent(data, name)) return [empty(name)];
  if (name === "rules") return rules(data, state);
  if (name === "last_session") return [session(data)];
  if (name === "threads") return threads(data);
  return [markdown(data.raw)];
}

async function load(state) {
  state.root.setAttribute("aria-busy", "true");
  state.bodies.forEach(body => body.replaceChildren(skeleton(3)));
  try {
    const data = await get("/api/v1/memory");
    if (active !== state) return;
    if (!names.some(name => sectionHasContent(data[name], name))) {
      state.navigation.hidden = true;
      state.layout.replaceChildren(emptyState(t("memory.emptyTitle"), t("memory.emptyMessage")));
    } else {
      names.forEach((name, index) => {
        state.bodies.get(sections[index]).replaceChildren(...content(name, data[name], state));
        const count = sectionCount(data[name], name);
        if (count !== null) {
          state.navigation.querySelector(`[data-tab="${sections[index]}"]`).textContent =
            t("memory.tabCount", { title: t(`memory.${name}.title`), count });
        }
      });
    }
    state.root.setAttribute("aria-busy", "false");
  } catch (error) {
    if (active !== state || error.code === "unauthorized") return;
    state.bodies.forEach(body => body.replaceChildren(errorState(t("memory.error"), () => void load(state))));
    state.root.setAttribute("aria-busy", "false");
  }
}

export function render(root, params = {}) {
  destroy();
  const state = { params, selected: sectionFromHash(`?${new URLSearchParams(params)}`),
    root: el("div", { class: "memory-page", "aria-busy": "true" }), bodies: new Map() };
  active = state;
  if (state.selected !== "kurallar") ruleQuery = "";
  state.navigation = tabs(sections.map((id, index) => ({ id, label: t(`memory.${names[index]}.title`) })), state.selected, id => {
    const query = new URLSearchParams(location.hash.split("?")[1] || "");
    query.set("bolum", id);
    location.hash = `#/hafiza?${query}`;
  });
  state.navigation.classList.add("memory-tabs");
  state.navigation.querySelectorAll("button").forEach((button, index) => button.setAttribute("aria-controls", `memory-${sections[index]}`));
  // One section at a time: the whole memory on one page was a long scroll past things not asked for.
  state.layout = el("div", { class: "memory-sections" }, sections.map((id, index) => {
    const body = el("div", { class: "stack memory-body" }, skeleton(3));
    state.bodies.set(id, body);
    const section = card(t(`memory.${names[index]}.title`), [body]);
    section.id = `memory-${id}`;
    section.classList.add("memory-section");
    section.setAttribute("role", "tabpanel");
    section.hidden = id !== state.selected;
    return section;
  }));
  state.root.append(el("header", { class: "page-heading" }, el("h1", {}, t("page.memory.title")),
    el("p", {}, t("page.memory.description"))), state.navigation, state.layout);
  root.replaceChildren(state.root);
  void load(state);
}

export function destroy() {
  active = null;
}
