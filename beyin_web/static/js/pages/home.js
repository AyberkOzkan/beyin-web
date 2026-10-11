import { get } from "../api.js";
import { el, icon } from "../dom.js";
import { t, messageList, formatDate, formatTime, relativeTime } from "../i18n.js";
import { errorState, skeleton, statusDot, illustrationSlot } from "../components/index.js";
import { preserveFocus } from "../accessibility.js";
import { greetingKey, firstSentence, dailyQuote, weeklyBars, changeKey } from "./home-model.js";

const definitions = [
  ["counts", "layers"], ["last_session", "history"], ["recent", "file-text", "#/bilgi"],
  ["projects", "folder-kanban", "#/projeler"], ["threads", "message-square", "#/hafiza"],
  ["week", "activity"], ["tasks", "list-todo"], ["upcoming", "calendar-days"],
];
let active;

function heading(key, name, href) {
  return el("div", { class: "card-title" }, icon(name), el("h2", { id: `home-title-${key}` }, t(`home.${key}.title`)),
    href && el("a", { class: "home-all", href }, t("home.viewAll"), icon("arrow-right")));
}

function section(key, name, href) {
  return el("section", { class: `card home-${key}`, id: `home-${key}`, "aria-labelledby": `home-title-${key}` },
    heading(key, name, href), el("div", { class: "home-body" }, skeleton(3)));
}

function empty(key) {
  return el("p", { class: "home-empty muted" }, t(`home.${key}.empty`));
}

function time(value, includeTime = false) {
  if (!value) return null;
  // Date-only values represent calendar days, not UTC midnight in the browser's zone.
  const date = value.length === 10 ? `${value}T12:00:00` : value;
  return el("time", { datetime: value, class: "muted" }, includeTime ?
    t("home.dateTime", { date: formatDate(date), time: formatTime(date) }) : formatDate(date));
}

function row(href, title, description = "", leading = "file-text", trailing = null, quiet = false) {
  return el("a", { href, class: `home-row${quiet ? " home-quiet" : ""}` },
    typeof leading === "string" ? icon(leading) : leading,
    el("div", { class: "home-row-copy" }, el("strong", {}, title), description && el("small", {}, description)), trailing);
}

function greeting(data) {
  const name = data.display_name?.trim() || "";
  return [el("div", { class: "home-welcome-copy" },
    el("h1", {}, t(greetingKey(data.period, name), { name })), el("p", {}, t("home.subtitle"))),
  el("div", { class: "home-welcome-aside" }, illustrationSlot("hero-saray"),
    el("blockquote", {}, dailyQuote(messageList("home.quotes"))))];
}

function counts(data) {
  const names = [["notes", "file-text"], ["knowledge", "book-open"], ["open_tasks", "list-todo"], ["receipts", "scroll-text"]];
  return [el("div", { class: "home-counters" }, names.map(([key, name]) => {
    const value = data?.[key] || { total: 0, last_7_days: 0 };
    return el("div", { class: "home-counter", "data-counter": key }, icon(name),
      el("strong", { class: "home-number" }, value.total), el("span", {}, t(`home.count.${key}`)),
      el("small", { class: value.last_7_days > 0 ? "home-increase" : "" }, t(changeKey(value.last_7_days), { count: value.last_7_days })));
  })), !names.some(([key]) => data?.[key]?.total) ? empty("counts") : null];
}

function lastSession(data) {
  if (!data) return [empty("last_session")];
  return [el("a", { class: "home-session-link", href: "#/hafiza" },
    el("strong", { class: "home-session-label" }, data.label), time(data.time || data.date, Boolean(data.time)),
    el("span", { class: "home-next-label" }, t("home.nextStep")),
    el("p", {}, data.next_step || t("home.noNextStep")))];
}

function recent(data) {
  return data.length ? data.map(record => row(`#/not/${encodeURIComponent(record.rid)}`, record.title, "", "file-text",
    el("time", { datetime: record.mtime, class: "home-relative muted" }, relativeTime(record.mtime)))) : [empty("recent")];
}

function projects(data) {
  return data.length ? data.map(project => row(`#/projeler/${encodeURIComponent(project.name)}`, project.name,
    t("home.noteCount", { count: project.note_count }), "folder-kanban", time(project.last_activity), project.quiet)) : [empty("projects")];
}

function threads(data) {
  return data.length ? data.map(thread => row("#/hafiza", thread.title, firstSentence(thread.next_step), "message-square",
    time(thread.status_date))) : [empty("threads")];
}

function tasks(data) {
  return [...(data.length ? data.map(task => row(`#/not/${encodeURIComponent(task.rid)}`, task.title,
    firstSentence(task.next_action), statusDot(task.status))) : [empty("tasks")]),
  el("a", { class: "home-footer-link", href: "#/projeler" }, t("home.allTasks"), icon("arrow-right"))];
}

function svgElement(tag, attributes = {}, text = null) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  if (text !== null) node.textContent = text;
  return node;
}

function week(data) {
  const bars = weeklyBars(data.days);
  const chart = svgElement("svg", { viewBox: "0 0 350 140", class: "home-chart", role: "img", "aria-label": t("home.week.chart") });
  const labels = messageList("home.week.days");
  chart.append(svgElement("line", { x1: 0, x2: 350, y1: 108, y2: 108, class: "home-chart-axis" }));
  bars.forEach((bar, index) => {
    const group = svgElement("g");
    group.append(svgElement("title", {}, t("home.week.bar", { date: formatDate(`${bar.date}T12:00:00`), count: bar.count })),
      svgElement("rect", { x: index * 50 + 12, y: 108 - bar.height, width: 26, height: bar.height, rx: 3, class: "home-chart-bar" }),
      svgElement("text", { x: index * 50 + 25, y: 134, "text-anchor": "middle" }, labels[index] || ""));
    chart.append(group);
  });
  return [el("div", { class: "home-week-content" }, chart,
    el("div", { class: "home-week-stats" },
      el("div", {}, icon("scroll-text"), el("p", {}, el("strong", { class: "home-number" }, data.receipts), el("span", {}, t("home.week.receipts")))),
      el("div", {}, icon("file-text"), el("p", {}, el("strong", { class: "home-number" }, data.changed), el("span", {}, t("home.week.changed")))))),
  !bars.some(bar => bar.count) && !data.changed ? empty("week") : null];
}

function upcoming(data) {
  return data.map(item => row(`#/not/${encodeURIComponent(item.record.rid)}`, item.record.title,
    t(`home.upcoming.${item.field}`), "calendar", time(item.date)));
}

const builders = { counts, last_session: lastSession, recent, projects, threads, week, tasks, upcoming };

function update(state, data) {
  state.cancelFocus?.();
  state.cancelFocus = preserveFocus(state.root);
  const scroll = [window.scrollX, window.scrollY];
  const today = new Date();
  const greetingSignature = JSON.stringify([data.greeting, today.getFullYear(), today.getMonth(), today.getDate()]);
  if (state.signatures.get("greeting") !== greetingSignature) {
    state.welcome.replaceChildren(...greeting(data.greeting));
    state.signatures.set("greeting", greetingSignature);
  }
  for (const [key, name, href] of definitions) {
    const signature = JSON.stringify(data[key]);
    if (state.signatures.get(key) === signature) continue;
    if (key === "upcoming" && !data.upcoming.length) {
      state.cards.get(key)?.remove();
      state.cards.delete(key);
    } else {
      let card = state.cards.get(key);
      if (!card) {
        card = section(key, name, href);
        state.cards.set(key, card);
        state.bottom.append(card);
      }
      const title = card.querySelector(".card-title") || heading(key, name, href);
      // replaceChildren() would print a missing optional part as the text "null".
      card.querySelector(".home-body").replaceChildren(...builders[key](data[key]).filter(Boolean));
      if (key === "last_session") {
        // The visible heading and content share one full-card link.
        const link = card.querySelector(".home-session-link");
        if (link) link.prepend(title);
        else card.prepend(title);
      }
    }
    state.signatures.set(key, signature);
  }
  state.bottom.classList.toggle("home-no-upcoming", !data.upcoming.length);
  state.feedback.replaceChildren();
  state.root.setAttribute("aria-busy", "false");
  window.scrollTo(...scroll);
}

async function load(state) {
  if (state.pending) { state.reload = true; return; }
  state.pending = true;
  state.root.setAttribute("aria-busy", "true");
  try {
    const data = await get("/api/v1/home");
    if (active === state) update(state, data);
  } catch (error) {
    if (active === state && error.code !== "unauthorized") {
      state.feedback.replaceChildren(errorState(t("home.error"), () => void load(state)));
      state.root.setAttribute("aria-busy", "false");
      if (!state.signatures.size) {
        state.welcome.replaceChildren(el("h1", {}, t("page.home.title")));
        state.cards.forEach(card => card.querySelector(".home-body").replaceChildren(el("p", { class: "muted" }, t("home.error"))));
      }
    }
  } finally {
    state.pending = false;
    if (state.reload && active === state) { state.reload = false; void load(state); }
  }
}

export const handlesChanges = true;

export function render(root) {
  destroy();
  const state = { root: el("div", { class: "home-page", "aria-busy": "true" }),
    welcome: el("header", { class: "home-welcome", id: "home-greeting" }, skeleton(2)),
    feedback: el("div", { class: "home-feedback" }), cards: new Map(), signatures: new Map(), pending: false, reload: false };
  active = state;
  const summary = el("div", { class: "home-summary" });
  const middle = el("div", { class: "home-middle" });
  state.bottom = el("div", { class: "home-bottom" });
  definitions.forEach(([key, name, href], index) => {
    // Upcoming items only acquire a slot after the API confirms they exist.
    if (key === "upcoming") return;
    const card = section(key, name, href);
    state.cards.set(key, card);
    (index < 2 ? summary : index < 5 ? middle : state.bottom).append(card);
  });
  state.root.append(state.welcome, state.feedback, summary, middle, state.bottom);
  root.replaceChildren(state.root);
  state.changed = () => void load(state);
  document.addEventListener("beyin:changed", state.changed);
  void load(state);
}

export function destroy() {
  active?.cancelFocus?.();
  if (active) document.removeEventListener("beyin:changed", active.changed);
  active = null;
}
