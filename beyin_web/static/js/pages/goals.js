import { get, post } from "../api.js";
import { el, icon } from "../dom.js";
import { t, formatDate } from "../i18n.js";
import { card, emptyState, errorState, skeleton, progressBar } from "../components/index.js";
import { monthFromParam, monthDays, monthLabel, monthNavigation, goalsHash, groupGoals, goalMeta,
  habitCount, goalPayload } from "./goals-model.js";

export const handlesChanges = true;
const definitions = [["long", "target"], ["year", "flag"], ["theme", "sun"], ["areas", "tag"], ["habits", "square-check"],
  ["trash", "history"]];
let active;
// What the reader had open survives a month change, which renders the page anew.
let kept = null;

function empty(key) {
  return emptyState(t(`goals.${key}.emptyTitle`), t(`goals.${key}.empty`));
}

function fail(state, error) {
  if (active !== state || error.code === "unauthorized") return;
  state.message.textContent = t(error.code === "conflict" ? "goals.conflict" :
    error.code === "read_only" ? "goals.readOnly" : "goals.saveError");
}

// Every change is one small request; the page then shows what the vault holds, not what was clicked.
function save(state, path, body, saved = () => {}) {
  const run = async () => {
    if (active !== state) return;
    state.pending += 1;
    state.message.textContent = "";
    state.root.setAttribute("aria-busy", "true");
    try {
      await post(path, body);
      saved();
    } catch (error) {
      fail(state, error);
    } finally {
      state.pending -= 1;
      if (active === state) await load(state, false);
    }
  };
  // Quick clicks are sent one after another, each against the file the previous one left.
  state.queue = state.queue.then(run, run);
  return state.queue;
}

function field(name, label, attributes = {}, tag = "input", hint = null) {
  return el("label", { class: "goals-field" }, el("span", {}, label), el(tag, { name, autocomplete: "off", ...attributes }),
    hint && el("small", {}, hint));
}

// Deleting asks once more, in place: a slip of the hand must not cost a goal.
function confirmBox(state, id, message, yes, run) {
  return el("div", { class: "goals-confirm", role: "group", "data-confirm": id }, el("p", {}, message),
    el("div", { class: "row" },
      el("button", { type: "button", class: "button goals-danger", onclick: () => { state.confirm = null; run(); } }, yes),
      el("button", { type: "button", class: "button", onclick: () => { state.confirm = null; draw(state); } }, t("goals.cancel"))));
}

function confirmDelete(state, kind, item) {
  return confirmBox(state, item.rid, t("goals.confirmDelete", { title: item.title }), t("goals.confirmYes"), () =>
    void save(state, `/api/v1/${kind}/${item.rid}/delete`, { title: item.title }, () => state.open.delete(item.rid)));
}

function deleteButton(state, item, content = null) {
  const label = t("goals.deleteLabel", { title: item.title });
  return el("button", { type: "button", class: content ? "goals-delete" : "goals-delete goals-delete-icon",
    "data-delete": item.rid, "aria-label": label, title: content ? null : label,
    onclick: () => { state.confirm = item.rid; draw(state); } }, content || icon("x"));
}

// Deleted goals and habits wait here: they can come back, or go for good after one more question.
function trash(state) {
  const { writable } = state.data;
  return [el("p", { class: "muted goals-trash-note" }, t("goals.trash.note")),
    el("ul", { class: "goals-trash" }, state.trash.map(item => {
      const key = `trash:${item.id}`;
      const body = { title: item.title };
      return el("li", { "data-trash": item.id },
        el("div", { class: "goals-trash-row" },
          el("span", { class: "goals-trash-title" }, el("strong", {}, item.title),
            el("small", {}, t(`goals.trash.kind.${item.kind}`))),
          writable && el("div", { class: "row" },
            el("button", { type: "button", class: "button", "data-restore": item.id,
              "aria-label": t("goals.trash.restoreLabel", { title: item.title }),
              onclick: () => void save(state, `/api/v1/goals/trash/${item.id}/restore`, body) }, t("goals.trash.restore")),
            el("button", { type: "button", class: "button", "data-purge": item.id,
              "aria-label": t("goals.trash.purgeLabel", { title: item.title }),
              onclick: () => { state.confirm = key; draw(state); } }, t("goals.trash.purge")))),
        state.confirm === key && confirmBox(state, key, t("goals.trash.confirm", { title: item.title }),
          t("goals.trash.confirmYes"), () => void save(state, `/api/v1/goals/trash/${item.id}/delete`, body)));
    }))];
}

function closeForm(state) {
  state.form = null;
  state.formNode = null;
}

// The form outlives the page state that opened it (a month change renders the page anew),
// so its buttons act on whichever state is current when they are pressed.
function form(key, fields, path, payload) {
  const node = el("form", { class: "goals-form", "data-form": key, novalidate: true }, fields,
    el("div", { class: "row" },
      el("button", { type: "submit", class: "button goals-primary" }, t("goals.save")),
      el("button", { type: "button", class: "button", onclick: () => { closeForm(active); draw(active); } }, t("goals.cancel"))));
  node.addEventListener("submit", event => {
    event.preventDefault();
    const state = active;
    const values = Object.fromEntries(new FormData(node));
    if (!values.title.trim()) { node.elements.title.focus(); return; }
    // A refused save keeps the form and what was typed into it.
    void save(state, path, payload(values), () => closeForm(state));
  });
  return node;
}

function goalForm(state, horizon) {
  const areas = el("datalist", { id: `goals-areas-${horizon}` }, state.data.areas.map(area => el("option", { value: area.name })));
  return form(horizon, [
    field("title", t("goals.field.title"), { maxlength: 120, required: true }),
    field("period", t("goals.field.period"), { maxlength: 40, placeholder: t(`goals.field.period.${horizon}`) }),
    field("area", t("goals.field.area"), { maxlength: 40, list: areas.id }, "input", t("goals.field.areaHint")), areas,
    field("steps", t("goals.field.steps"), { rows: 4 }, "textarea"),
  ], "/api/v1/goals", values => goalPayload(horizon, values));
}

function habitForm() {
  return form("habits", [field("title", t("goals.field.habit"), { maxlength: 120, required: true })],
    "/api/v1/habits", values => ({ title: values.title.trim() }));
}

function addButton(state, key) {
  if (!state.data.writable || state.form === key) return null;
  return el("button", { type: "button", class: "button goals-add", "data-add": key, onclick: () => {
    state.form = key;
    state.formNode = key === "habits" ? habitForm() : goalForm(state, key);
    draw(state);
    state.formNode.elements.title.focus();
  } }, t(`goals.${key}.add`));
}

function goalRow(state, goal) {
  const meta = goalMeta(goal);
  const steps = goal.steps.map(step => el("li", {}, el("label", { class: "goals-step" },
    el("input", { type: "checkbox", checked: step.done, disabled: !state.data.writable, onchange: event =>
      void save(state, `/api/v1/goals/${goal.rid}/steps/${step.index}`, { done: event.target.checked, text: step.text }) }),
    el("span", {}, step.text))));
  const details = el("details", { class: "goals-goal", "data-rid": goal.rid, open: state.open.has(goal.rid) },
    el("summary", {}, el("span", { class: "goals-goal-title" }, el("strong", {}, goal.title), meta && el("small", {}, meta)),
      goal.total ? progressBar(goal.done, goal.total, t("goals.progress", { title: goal.title })) :
        el("small", { class: "muted" }, t("goals.noSteps"))),
    goal.summary && el("p", {}, goal.summary),
    steps.length ? el("ul", { class: "goals-steps" }, steps) : null,
    state.confirm === goal.rid ? confirmDelete(state, "goals", goal) : el("div", { class: "row goals-row-actions" },
      el("a", { class: "goals-note", href: `#/not/${goal.rid}` }, t("goals.openNote")),
      state.data.writable && deleteButton(state, goal, t("goals.delete"))));
  details.addEventListener("toggle", () => {
    if (details.open) state.open.add(goal.rid);
    else state.open.delete(goal.rid);
  });
  return details;
}

function goalList(state, key, goals) {
  return [state.form === key ? state.formNode : null,
    goals.length ? el("div", { class: "goals-list" }, goals.map(goal => goalRow(state, goal))) : empty(key)];
}

function theme(data) {
  const item = data.theme;
  return [el("div", { class: "goals-theme" }, item.period && el("strong", { class: "goals-theme-period" }, item.period),
    el("div", {}, el("h3", {}, el("a", { href: `#/not/${item.rid}` }, item.title)), item.summary && el("p", {}, item.summary)))];
}

function areas(data) {
  if (!data.areas.length) return [empty("areas")];
  return [el("ul", { class: "goals-areas" }, data.areas.map(area => el("li", { "data-area": area.name },
    el("strong", {}, area.name), el("small", {}, t("goals.areas.count", { count: area.goals })),
    area.total ? progressBar(area.done, area.total, t("goals.progress", { title: area.name })) : null)))];
}

function habits(state) {
  const { data, month } = state;
  const days = monthDays(month);
  const navigation = monthNavigation(month, data.today);
  const move = (target, key) => el("button", { type: "button", class: "icon-button", disabled: !target,
    "aria-label": t(`goals.habits.${key}`), "data-month": key,
    onclick: () => { location.hash = goalsHash(target, data.today); } }, icon(key === "previous" ? "chevron-left" : "chevron-right"));
  const header = el("div", { class: "row goals-month" }, move(navigation.previous, "previous"),
    el("strong", { class: "goals-month-label" }, monthLabel(month)), move(navigation.next, "next"));
  if (!data.habits.length) return [header, state.form === "habits" ? state.formNode : null, empty("habits")];
  const rows = data.habits.map(habit => {
    const done = new Set(habit.days);
    return el("tr", { "data-rid": habit.rid },
      el("th", { scope: "row" }, el("span", { class: "goals-habit-title" }, habit.title,
        data.writable && deleteButton(state, habit)),
      el("small", {}, t("goals.habits.count", { count: habitCount(habit, month) }))),
      days.map(day => el("td", {}, el("button", { type: "button", class: "goals-day", "data-day": day,
        "aria-pressed": String(done.has(day)), disabled: day > data.today || !data.writable,
        "aria-label": t("goals.habits.day", { title: habit.title, date: formatDate(`${day}T12:00:00`) }),
        onclick: () => void save(state, `/api/v1/habits/${habit.rid}/days/${day}`, { done: !done.has(day) }) },
      done.has(day) ? icon("check") : null))));
  });
  const doomed = data.habits.find(habit => habit.rid === state.confirm);
  return [header, state.form === "habits" ? state.formNode : null, doomed ? confirmDelete(state, "habits", doomed) : null,
    el("div", { class: "goals-table-wrap" }, el("table", { class: "goals-table" },
      el("thead", {}, el("tr", {}, el("th", { scope: "col" }, t("goals.habits.name")),
        days.map(day => el("th", { scope: "col", class: day === data.today ? "goals-today" : null }, Number(day.slice(8)))))),
      el("tbody", {}, rows)))];
}

function draw(state) {
  const { data } = state;
  const groups = groupGoals(data.goals);
  const content = { long: () => goalList(state, "long", groups.long), year: () => goalList(state, "year", groups.year),
    theme: () => theme(data), areas: () => areas(data), habits: () => habits(state), trash: () => trash(state) };
  state.notice.hidden = data.writable;
  for (const [key, section] of state.sections) {
    section.hidden = (key === "theme" && !data.theme) || (key === "trash" && !state.trash.length);
    if (section.hidden) continue;
    section.querySelector(".goals-actions").replaceChildren(...[["long", "year", "habits"].includes(key) ? addButton(state, key) : null].filter(Boolean));
    section.querySelector(".goals-body").replaceChildren(...content[key]().filter(Boolean));
  }
}

// A vault change elsewhere reaches this page as "something changed"; when none of it concerns the
// goals, the page is left as it is: redrawing would take the control under the reader's hand away.
async function load(state, showSkeleton = true, always = true) {
  const request = ++state.request;
  state.root.setAttribute("aria-busy", "true");
  if (showSkeleton) state.sections.forEach(section => section.querySelector(".goals-body").replaceChildren(skeleton(3)));
  try {
    const [data, discarded] = await Promise.all([get("/api/v1/goals"), get("/api/v1/goals/trash")]);
    if (active !== state || request !== state.request) return;
    const month = monthFromParam(state.params.ay, data.today);
    const shown = JSON.stringify([{ ...data, generation: null }, discarded.items, month]);
    const unchanged = shown === state.shown;
    state.data = data;
    state.trash = discarded.items;
    state.month = month;
    state.shown = shown;
    if (always || !unchanged) draw(state);
  } catch (error) {
    if (active !== state || request !== state.request || error.code === "unauthorized") return;
    state.sections.forEach(section => section.querySelector(".goals-body").replaceChildren(
      errorState(t("goals.error"), () => void load(state))));
  }
  if (active === state && request === state.request) state.root.setAttribute("aria-busy", "false");
}

export function render(root, params = {}) {
  destroy();
  const state = { params, request: 0, pending: 0, queue: Promise.resolve(), form: kept?.form ?? null,
    formNode: kept?.formNode ?? null, open: kept?.open ?? new Set(), confirm: kept?.confirm ?? null,
    sections: new Map(), root: el("div", { class: "goals-page", "aria-busy": "true" }) };
  kept = null;
  active = state;
  state.notice = el("p", { class: "goals-notice", hidden: true }, icon("lock"), t("goals.readOnly"));
  state.message = el("p", { class: "goals-message", role: "alert" });
  const grid = el("div", { class: "goals-grid" }, definitions.map(([key, name]) => {
    const section = card(t(`goals.${key}.title`), [el("div", { class: "goals-body" }, skeleton(3))], name);
    section.id = `goals-${key}`;
    section.querySelector(".card-title").append(el("div", { class: "goals-actions" }));
    state.sections.set(key, section);
    return section;
  }));
  state.root.append(el("header", { class: "page-heading" }, el("h1", {}, t("page.goals.title")),
    el("p", {}, t("page.goals.description"))), state.notice, state.message, grid);
  state.changed = () => { if (!state.pending) void load(state, false, false); };
  document.addEventListener("beyin:changed", state.changed);
  root.replaceChildren(state.root);
  void load(state);
}

export function destroy() {
  if (active) {
    document.removeEventListener("beyin:changed", active.changed);
    kept = { form: active.form, formNode: active.formNode, open: active.open, confirm: active.confirm };
  }
  active = null;
}
