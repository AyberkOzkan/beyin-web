import { el, icon } from "../dom.js";
import { t } from "../i18n.js";

const statuses = new Set(["inbox", "active", "waiting", "blocked", "done", "cancelled", "unknown"]);
const kinds = new Set(["note", "knowledge", "task", "receipt", "memory", "index", "rejected"]);

export function obsidianTarget(vaultUri, recordUri = null) {
  const href = recordUri ?? vaultUri;
  if (typeof href !== "string" || !href.startsWith("obsidian://open?")) return null;
  return { href, labelKey: recordUri === null ? "shell.openVaultObsidian" : "shell.openRecordObsidian" };
}

export function card(title, children = [], iconName = null) {
  return el("section", { class: "card" },
    el("div", { class: "card-title" }, iconName && icon(iconName), el("h2", {}, title)), children);
}

export function listRow({ title, description = "", leading = "file-text", trailing = null, href = null, selected = false }) {
  return el(href ? "a" : "div", {
    class: `list-row${selected ? " list-row-selected" : ""}`, href,
    "aria-current": selected && href ? "page" : null,
  }, leading && icon(leading), el("div", { class: "list-row-content" },
    el("strong", {}, title), description && el("small", {}, description)), trailing);
}

export function badge(value, category = "kind") {
  const valid = category === "status" ? statuses : kinds;
  const key = valid.has(value) ? value : "unknown";
  return el("span", { class: `badge tone-${key}` }, t(`${category}.${key}`));
}

export function statusDot(status = "active", label = null) {
  const key = statuses.has(status) ? status : "unknown";
  return el("span", {
    class: `status-dot tone-${key}`, role: "img", "aria-label": label || t(`status.${key}`),
  });
}

export function progressBar(value = 0, maximum = 100, label = t("component.progress")) {
  const max = Number.isFinite(maximum) && maximum > 0 ? maximum : 100;
  const current = Number.isFinite(value) ? Math.min(max, Math.max(0, value)) : 0;
  return el("div", { class: "progress" },
    el("meter", { min: 0, max, value: current, "aria-label": label }, current),
    el("small", {}, t("component.progressValue", { current, max })));
}

export function tabs(items, selected, onChange = () => {}) {
  const root = el("div", { class: "tabs", role: "tablist", "aria-label": t("component.tabs") });
  const buttons = items.map(item => el("button", {
    type: "button", class: "tab", role: "tab", disabled: item.disabled,
    "aria-selected": String(item.id === selected), "data-tab": item.id, tabindex: item.id === selected ? 0 : -1,
    onclick: () => select(item.id),
  }, item.label));
  function select(id) {
    buttons.forEach((button, index) => {
      const active = items[index].id === id;
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    });
    onChange(id);
  }
  root.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const enabled = buttons.filter(button => !button.disabled);
    const current = enabled.indexOf(document.activeElement);
    let index = event.key === "Home" ? 0 : event.key === "End" ? enabled.length - 1 :
      (current + (event.key === "ArrowRight" ? 1 : -1) + enabled.length) % enabled.length;
    if (!enabled[index]) return;
    event.preventDefault();
    enabled[index].click();
    enabled[index].focus();
  });
  root.append(...buttons);
  return root;
}

export function filterBox({ label = t("component.filter"), value = "", disabled = false, onInput = () => {} } = {}) {
  return el("label", { class: "filter-box" }, icon("search"),
    el("input", { type: "search", "aria-label": label, placeholder: label, value, disabled,
      oninput: event => onInput(event.target.value) }));
}

export function emptyState(title = t("state.emptyTitle"), message = t("state.emptyMessage")) {
  return el("div", { class: "state" }, illustrationSlot("card-window", drawings, title) || icon("inbox"),
    el("strong", { class: "state-title" }, title), el("p", {}, message));
}

export function errorState(message = t("state.errorMessage"), retry = null) {
  return el("div", { class: "state", role: "alert" }, icon("circle-alert"),
    el("strong", { class: "state-title" }, t("state.errorTitle")), el("p", {}, message),
    retry && el("button", { class: "button", type: "button", onclick: retry }, icon("refresh-cw"), t("action.retry")));
}

export function skeleton(lines = 3) {
  return el("div", { class: "skeleton", role: "status", "aria-label": t("state.loading") },
    Array.from({ length: Math.max(1, Math.min(10, lines)) }, () => el("div", { class: "skeleton-line", "aria-hidden": "true" })));
}

let drawings = {};

export function setDrawings(value) {
  drawings = { ...value };
}

const SLOTS = ["hero-palace", "sidebar-tree", "heading-mountains", "card-window"];
const chosen = new Map();

// A slot may hold several drawings. One is picked at random for each place and kept until the page is loaded again,
// so a redraw does not swap the picture under the reader's eyes.
export function illustrationSlot(name, available = drawings, place = "") {
  if (!SLOTS.includes(name)) return null;
  const local = new RegExp(`^/static/img/${name}(-[a-z0-9]+)*\\.(png|svg|webp)$`);
  const sources = [available[name]].flat().filter(source => typeof source === "string" && local.test(source));
  if (!sources.length) return null;
  const key = `${name}:${place}`;
  if (!sources.includes(chosen.get(key))) chosen.set(key, sources[Math.floor(Math.random() * sources.length)]);
  return el("img", { class: `illustration illustration-${name}`, src: chosen.get(key), alt: "", onerror: event => event.target.remove() });
}

export function headingArt(page) {
  return illustrationSlot("heading-mountains", drawings, page);
}
