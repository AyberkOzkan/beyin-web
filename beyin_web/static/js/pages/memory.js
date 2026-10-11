import { get } from "../api.js";
import { el } from "../dom.js";
import { t, formatDate, formatTime } from "../i18n.js";
import { mountMarkdown } from "../markdown.js";
import { scrollTo } from "../accessibility.js";
import { card, tabs, emptyState, errorState, skeleton } from "../components/index.js";
import { sections, sectionFromHash, scopeList, filterRules, sectionHasContent } from "./memory-model.js";

const names = ["identity", "rules", "last_session", "threads"];
let active = null;

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

function ruleCard(item) {
  if (!item.date) return el("article", { class: "card memory-rule" }, el("p", {}, item.text));
  return el("article", { class: "card memory-rule" },
    el("div", { class: "row memory-meta" }, date(item.date),
      item.scope && el("span", { class: "badge memory-scope" }, item.scope)),
    el("h3", {}, item.title), el("p", {}, item.text),
    (item.reason || item.source) && el("details", { class: "memory-reason" },
      el("summary", {}, t("memory.why")),
      item.reason && field(t("memory.reason"), item.reason),
      item.source && field(t("memory.source"), item.source)));
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
  return [el("label", { class: "memory-filter", for: "memory-scope" }, t("memory.scopeFilter"), select),
    el("div", { class: "stack memory-rules" }, filterRules(data.items, scope).map(ruleCard))];
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
  if (name === "identity" && data.records?.some(record => record.body?.trim())) {
    return data.records.filter(record => record.body?.trim()).map(record => markdown(record.body));
  }
  if (data.structured === false) return data.raw?.trim() ? [markdown(data.raw)] : [empty(name)];
  if (!sectionHasContent(data, name)) return [empty(name)];
  if (name === "rules") return rules(data, state);
  if (name === "last_session") return [session(data)];
  if (name === "threads") return threads(data);
  return [markdown(data.raw)];
}

function scrollToSection(state) {
  if (active !== state || !state.params.bolum) return;
  scrollTo(state.bodies.get(state.selected)?.parentElement);
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
      names.forEach((name, index) => state.bodies.get(sections[index]).replaceChildren(...content(name, data[name], state)));
    }
    state.root.setAttribute("aria-busy", "false");
    scrollToSection(state);
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
  state.navigation = tabs(sections.map((id, index) => ({ id, label: t(`memory.${names[index]}.title`) })), state.selected, id => {
    const query = new URLSearchParams(location.hash.split("?")[1] || "");
    query.set("bolum", id);
    const hash = `#/hafiza?${query}`;
    if (location.hash === hash) scrollToSection(state);
    else location.hash = hash;
  });
  state.navigation.classList.add("memory-tabs");
  state.navigation.querySelectorAll("button").forEach((button, index) => button.setAttribute("aria-controls", `memory-${sections[index]}`));
  state.layout = el("div", { class: "stack memory-sections" }, sections.map((id, index) => {
    const body = el("div", { class: "stack memory-body" }, skeleton(3));
    state.bodies.set(id, body);
    const section = card(t(`memory.${names[index]}.title`), [body]);
    section.id = `memory-${id}`;
    section.classList.add("memory-section");
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
