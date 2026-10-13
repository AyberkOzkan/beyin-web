import { get } from "../api.js";
import { el, icon } from "../dom.js";
import { t, messageList, formatDate, currentLocale } from "../i18n.js";
import { headingArt, card, emptyState, errorState, skeleton, progressBar } from "../components/index.js";
import { weeklyBars } from "./home-model.js";
import { activeDaysLabel, dailyPoints, percentage, rangeLabel, weekNavigation } from "./reports-model.js";

const definitions = [["week", "calendar-days"], ["month", "activity"],
  ["projects", "folder-kanban"], ["knowledge", "layers"], ["learned", "lightbulb"]];
let active;

function empty(key) {
  return emptyState(t("reports.emptyTitle"), t(`reports.${key}.empty`));
}

function svg(tag, attributes = {}, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
  if (text !== undefined) node.textContent = text;
  return node;
}

function dateLabel(date) {
  return formatDate(`${date}T12:00:00`);
}

function chart(period, key) {
  const root = svg("svg", { viewBox: "0 0 360 140", class: "reports-chart", role: "img",
    "aria-label": t(`reports.${key}.chart`, {
      range: rangeLabel(period.start, period.end), count: period.receipts,
    }) });
  root.append(svg("line", { x1: 0, x2: 360, y1: 108, y2: 108, class: "reports-axis" }));
  if (key === "week") {
    const labels = messageList("reports.week.days");
    weeklyBars(period.days).forEach((bar, index) => {
      const rectangle = svg("rect", { x: index * 51 + 13, y: 108 - bar.height,
        width: 26, height: bar.height, rx: 3, class: "reports-bar" });
      rectangle.append(svg("title", {}, t("reports.chartPoint", { date: dateLabel(bar.date), count: bar.count })));
      root.append(rectangle, svg("text", { x: index * 51 + 26, y: 133, "text-anchor": "middle" }, labels[index]));
    });
  } else {
    const points = dailyPoints(period.days, 350, 100);
    const path = points.map((point, index) => `${index ? "L" : "M"}${point.x + 5},${point.y + 8}`).join(" ");
    root.append(svg("path", { d: `${path} L355,108 L5,108 Z`, class: "reports-area" }),
      svg("path", { d: path, class: "reports-line" }));
    points.forEach(point => {
      const dot = svg("circle", { cx: point.x + 5, cy: point.y + 8, r: 2, class: "reports-dot" });
      dot.append(svg("title", {}, t("reports.chartPoint", { date: dateLabel(point.date), count: point.count })));
      root.append(dot);
    });
    const dates = Object.keys(period.days);
    [0, Math.floor((dates.length - 1) / 2), dates.length - 1].forEach((index, position) => {
      root.append(svg("text", { x: [5, 180, 355][position], y: 133,
        "text-anchor": ["start", "middle", "end"][position] },
      new Intl.DateTimeFormat(currentLocale(), { day: "numeric", month: "short" }).format(new Date(`${dates[index]}T12:00:00`))));
    });
  }
  return root;
}

function stats(period, key) {
  return el("dl", { class: "reports-stats" }, ["receipts", "active_days", "worked_notes", "learned_count"].map(name =>
    el("div", { "data-stat": name }, el("dt", {}, t(`reports.stat.${name}`)),
      el("dd", {}, el("strong", {}, name === "active_days" ? activeDaysLabel(period[name], key === "week" ? 7 : 30) : period[name])),
      name === "receipts" && el("small", {}, t(`reports.${key}.previous`, { count: period.previous_receipts })))));
}

function periodCard(period, key) {
  return [el("div", { class: "reports-period" }, period.receipts ? chart(period, key) : empty(key), stats(period, key))];
}

function projectRows(projects) {
  return projects.length ? projects.map(project => el("article", {
    class: `reports-project${project.quiet ? " reports-quiet" : ""}`, "data-project": project.name,
  }, el("a", { href: `#/projeler/${encodeURIComponent(project.name)}` }, el("h3", {}, project.title)),
  project.total ? progressBar(project.done, project.total) : el("p", { class: "muted" }, t("projects.noTasks")),
  el("p", { class: "reports-project-receipts" }, t("reports.projectReceipts", { week: project.week_receipts, month: project.month_receipts })),
  el("small", {}, t("reports.openTasks", { count: project.open_tasks })))) : [empty("projects")];
}

function knowledgeCard(data, projects) {
  const titles = new Map(projects.map(project => [project.name, project.title]));
  const maximum = Math.max(1, ...data.by_project.map(group => group.notes + group.knowledge));
  return [el("div", { class: "reports-counts" }, Object.entries(data.counts).map(([key, count]) =>
    el("div", { "data-count": key }, el("strong", {}, count), el("span", {}, t(`reports.count.${key}`))))),
  !Object.values(data.counts).some(Boolean) && empty("knowledge"),
  el("h3", {}, t("reports.byProject")),
  ...(data.by_project.length ? data.by_project.map(group => {
    const count = group.notes + group.knowledge;
    // Without this the 100×8 box keeps its ratio and the bar is drawn 100px wide in the middle of the track.
    const bar = svg("svg", { viewBox: "0 0 100 8", preserveAspectRatio: "none", class: "reports-distribution-bar", "aria-hidden": "true" });
    bar.append(svg("rect", { width: percentage(count, maximum), height: 8, class: "reports-bar" }));
    const name = group.project === null ? t("reports.general") : titles.get(group.project) || group.project;
    return el("div", { class: "reports-distribution", "data-project": group.project ?? "" }, el("span", {}, name), bar, el("strong", {}, count));
  }) : [empty("byProject")]),
  el("h3", {}, t("reports.mostWorked")),
  ...(data.most_worked.length ? data.most_worked.map(item => el("a", {
    class: "reports-worked", href: `#/not/${encodeURIComponent(item.record.rid)}`,
  }, el("strong", {}, item.record.title), el("small", {}, t("reports.receiptCount", { count: item.receipts })))) : [empty("mostWorked")])].filter(Boolean);
}

function learnedRows(items) {
  return items.length ? items.map(item => el("a", { class: "reports-learned", href: `#/gunlukler/${item.day}` },
    el("time", { datetime: item.time }, t("reports.learnedTime", { date: dateLabel(item.day), time: item.time.slice(11, 16) })),
    el("p", {}, item.text), el("div", { class: "row" }, item.projects.map(project => el("span", { class: "badge" }, project))))) : [empty("learned")];
}

function navigate(week) {
  location.hash = week ? `/raporlar?hafta=${week}` : "/raporlar";
}

function paint(state, data) {
  const neighbors = weekNavigation(data.week.start, data.today);
  state.root.dataset.week = data.week.start;
  state.navigation.replaceChildren(
    el("button", { id: "reports-previous", type: "button", class: "icon-button", "aria-label": t("reports.previousWeek"),
      "data-week": neighbors.previous }, icon("chevron-left")),
    el("strong", { id: "reports-range" }, rangeLabel(data.week.start, data.week.end)),
    el("button", { id: "reports-next", type: "button", class: "icon-button", "aria-label": t("reports.nextWeek"),
      disabled: !neighbors.next, "data-week": neighbors.next }, icon("chevron-right")),
    el("button", { id: "reports-current", type: "button", class: "button", disabled: neighbors.isCurrent,
      "data-current": true }, t("reports.currentWeek")));
  const contents = { week: periodCard(data.week, "week"), month: periodCard(data.month, "month"),
    projects: projectRows(data.projects), knowledge: knowledgeCard(data.knowledge, data.projects), learned: learnedRows(data.learned) };
  for (const [key, body] of state.bodies) body.replaceChildren(...contents[key]);
}

async function load(state) {
  const request = ++state.request;
  state.root.setAttribute("aria-busy", "true");
  state.bodies.forEach(body => body.replaceChildren(skeleton()));
  try {
    const data = await get("/api/v1/reports", state.week ? { week: state.week } : {});
    if (active === state && state.request === request) paint(state, data);
  } catch (error) {
    if (active !== state || state.request !== request || error.code === "unauthorized") return;
    state.bodies.forEach(body => {
      const failure = errorState(t("reports.error"));
      failure.append(el("button", { type: "button", class: "button", "data-retry": true },
        icon("refresh-cw"), t("action.retry")));
      body.replaceChildren(failure);
    });
  } finally {
    if (active === state && state.request === request) state.root.setAttribute("aria-busy", "false");
  }
}

export function render(root, params = {}) {
  destroy();
  const state = { root: el("div", { class: "reports-page", "aria-busy": "true" }),
    week: params.hafta || "", bodies: new Map(), request: 0,
    navigation: el("nav", { class: "reports-navigation", "aria-label": t("reports.weekSelection") }, skeleton(1)) };
  active = state;
  state.click = event => {
    const button = event.target.closest("button");
    if (!button || button.disabled || active !== state) return;
    if (button.hasAttribute("data-retry")) void load(state);
    else if (button.hasAttribute("data-current")) navigate();
    else if (button.dataset.week) navigate(button.dataset.week);
  };
  state.root.addEventListener("click", state.click);
  const grid = el("div", { class: "reports-grid" });
  for (const [key, name] of definitions) {
    const body = el("div", { class: "reports-body" }, skeleton());
    const section = card(t(`reports.${key}.title`), [body], name);
    section.id = `reports-${key}`;
    state.bodies.set(key, body);
    grid.append(section);
  }
  state.root.append(el("header", { class: "page-heading" }, el("h1", {}, t("page.reports.title")),
    el("p", {}, t("page.reports.description")), el("p", { class: "reports-notice" }, icon("info"), t("reports.notice")), headingArt("reports")),
  state.navigation, grid);
  root.replaceChildren(state.root);
  void load(state);
}

export function destroy() {
  if (active) active.root.removeEventListener("click", active.click);
  active = null;
}
