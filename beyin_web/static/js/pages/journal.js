import { get } from "../api.js";
import { el, icon } from "../dom.js";
import { t, formatDate } from "../i18n.js";
import { preserveFocus } from "../accessibility.js";
import { card, emptyState, errorState, listRow, skeleton, statusDot } from "../components/index.js";
import { calendar } from "../components/calendar.js";
import { heatmap } from "../components/heatmap.js";
import { timeline } from "../components/timeline.js";
import { adjacentReceiptDays, clockText, dayLabel, daySummary, isDate, latestReceiptDay, receiptDays, shiftMonth, upcomingGroups } from "./journal-model.js";
import { firstSentence } from "./home-model.js";

let active;

function section(key, name) {
  const body = el("div", { class: "journal-body" }, skeleton());
  const root = card(t(`journal.${key}.title`), [body], name);
  root.id = `journal-${key}`;
  return { root, body };
}

function empty(key) {
  return emptyState(t("journal.emptyTitle"), t(`journal.${key}.empty`));
}

function failure(message, retry) {
  const root = errorState(message);
  root.append(el("button", { type: "button", class: "button", "data-retry": retry },
    icon("refresh-cw"), t("action.retry")));
  return root;
}

function paintCalendar(state) {
  if (!state.monthData) return;
  if (state.calendar.body.contains(document.activeElement)) {
    state.cancelCalendarFocus?.();
    state.cancelCalendarFocus = preserveFocus(state.calendar.body);
  }
  const days = state.monthData.days;
  state.calendar.body.replaceChildren(calendar({
    month: state.month, days, selected: state.date, today: state.heatData?.today,
  }));
  if (!receiptDays(days).length) state.calendar.body.append(el("p", { class: "muted journal-calendar-empty" }, t("journal.month.empty")));
  const dates = receiptDays(days).reverse();
  state.monthDays.body.replaceChildren(...(dates.length ? dates.map(date => listRow({
    title: Number(date.slice(8)), description: dayLabel(date), leading: null,
    trailing: el("small", { class: "journal-month-count" }, t("journal.count", { count: days[date] })),
    href: `#/gunlukler/${date}`, selected: date === state.date,
  })) : [empty("month")]));
}

function paintNavigation(state) {
  const neighbors = adjacentReceiptDays(state.heatData?.days, state.date);
  state.navigation.replaceChildren(...["previous", "next"].map(direction => el("button", {
    type: "button", class: `icon-button journal-${direction}-day`,
    "data-day": neighbors[direction], disabled: !neighbors[direction],
    "aria-label": t(`journal.${direction}Day`),
  }, icon(direction === "previous" ? "chevron-left" : "chevron-right"))));
}

function paintDay(state, data) {
  const summary = daySummary(data);
  state.summary.body.replaceChildren(el("div", { class: "journal-summary-grid" },
    [["receipts", "receipt"], ["workedNotes", "file-text"], ["learned", "lightbulb"], ["sessions", "history"]].map(([key, name]) =>
      el("div", { class: "journal-summary-tile", role: "img", "data-summary": key,
        "aria-label": t(`journal.summary.${key}.label`, { count: summary[key] }) },
      el("div", { class: "journal-summary-content", "aria-hidden": "true" }, icon(name),
        el("strong", { class: "journal-summary-number" }, summary[key]), el("span", {}, t(`journal.summary.${key}`)))))));
  state.sessions.root.hidden = !data.cards.length;
  state.sessions.body.replaceChildren(...data.cards.map(session => el("article", { class: "journal-session" },
    el("div", { class: "row" }, el("h3", {}, session.label),
      session.time && el("time", { datetime: session.time }, clockText(session.time))),
    el("dl", {}, session.items.map(([label, value]) =>
      el("div", { class: "journal-session-item" }, el("dt", {}, label), el("dd", {}, value)))))));
  state.timeline.body.replaceChildren(data.receipts.length ? timeline(data.receipts) : empty("day"));
  state.changed.body.replaceChildren(...(data.changed.length ? data.changed.map(record => listRow({
    href: `#/not/${encodeURIComponent(record.rid)}`, title: record.title,
  })) : [empty("changed")]));
}

function upcomingRow(title, description, rid, leading, date) {
  return el("a", { class: "journal-upcoming-row", href: `#/not/${encodeURIComponent(rid)}` },
    date && el("time", { class: "journal-upcoming-date", datetime: date }, formatDate(`${date}T12:00:00`)),
    el("div", { class: "journal-upcoming-details" }, leading,
      el("div", { class: "journal-upcoming-copy" }, el("strong", {}, title), el("small", {}, description))));
}

function paintUpcoming(state, home) {
  const { dated, steps, moreDated, moreSteps } = upcomingGroups(home);
  if (!dated.length && !steps.length) {
    state.upcoming.body.replaceChildren(empty("upcoming"));
    return;
  }
  const group = (key, rows, more) => el("div", { class: `journal-upcoming-group journal-upcoming-${key}` },
    el("h3", {}, t(`journal.upcoming.${key}`)),
    rows.length ? rows : el("p", { class: "journal-upcoming-empty" }, t(`journal.upcoming.${key}.empty`)),
    more > 0 && el("p", { class: "journal-upcoming-more" }, t("journal.upcoming.more", { count: more })));
  state.upcoming.body.replaceChildren(
    group("dated", dated.map(item => upcomingRow(item.record.title, t(`home.upcoming.${item.field}`),
      item.record.rid, icon(item.field === "due_at" ? "flag" : "calendar"), item.date)), moreDated),
    group("steps", steps.map(task => upcomingRow(task.title, firstSentence(task.next_action),
      task.rid, statusDot(task.status))), moreSteps));
}

async function loadUpcoming(state) {
  if (active !== state) return;
  const request = ++state.upcomingRequest;
  busy(state, "upcoming", true);
  state.upcoming.body.replaceChildren(skeleton());
  try {
    // The shell recreates this page on every day change; api.js answers the repeat from its ETag cache.
    const data = await get("/api/v1/home");
    if (active === state && request === state.upcomingRequest) paintUpcoming(state, data);
  } catch (error) {
    if (active !== state || request !== state.upcomingRequest || error.code === "unauthorized") return;
    state.upcoming.body.replaceChildren(failure(t("journal.upcoming.error"), "upcoming"));
  } finally {
    if (active === state && request === state.upcomingRequest) busy(state, "upcoming", false);
  }
}

function busy(state, key, value) {
  state.pending[key] = value;
  state.root.setAttribute("aria-busy", String(Object.values(state.pending).some(Boolean)));
}

async function loadMonth(state, month) {
  if (active !== state) return;
  state.cancelCalendarFocus?.();
  state.cancelCalendarFocus = preserveFocus(state.calendar.body);
  state.month = month;
  state.monthData = null;
  const request = ++state.monthRequest;
  busy(state, "month", true);
  state.calendar.body.replaceChildren(skeleton());
  state.monthDays.body.replaceChildren(skeleton());
  try {
    const data = await get(`/api/v1/journal/months/${month}`);
    if (active !== state || request !== state.monthRequest) return;
    state.monthData = data;
    paintCalendar(state);
  } catch (error) {
    if (active !== state || request !== state.monthRequest || error.code === "unauthorized") return;
    for (const part of [state.calendar, state.monthDays]) {
      part.body.replaceChildren(failure(t("journal.month.error"), "month"));
    }
  } finally {
    if (active === state && request === state.monthRequest) busy(state, "month", false);
  }
}

async function loadDay(state) {
  if (active !== state) return;
  const request = ++state.dayRequest;
  busy(state, "day", true);
  state.sessions.root.hidden = false;
  for (const part of [state.summary, state.sessions, state.timeline, state.changed]) part.body.replaceChildren(skeleton());
  try {
    const data = await get(`/api/v1/journal/days/${state.date}`);
    if (active === state && request === state.dayRequest) paintDay(state, data);
  } catch (error) {
    if (active !== state || request !== state.dayRequest || error.code === "unauthorized") return;
    for (const part of [state.summary, state.sessions, state.timeline, state.changed]) {
      part.body.replaceChildren(failure(t("journal.day.error"), "day"));
    }
  } finally {
    if (active === state && request === state.dayRequest) busy(state, "day", false);
  }
}

async function loadHeatmap(state) {
  if (active !== state) return;
  const request = ++state.heatRequest;
  busy(state, "heatmap", true);
  state.heatmap.body.replaceChildren(skeleton());
  try {
    const data = await get("/api/v1/journal/heatmap", { weeks: 20 });
    if (active !== state || request !== state.heatRequest) return;
    state.heatData = data;
    if (!state.date) {
      location.replace(`#/gunlukler/${latestReceiptDay(data.days, data.today)}`);
      return;
    }
    state.heatmap.body.replaceChildren(heatmap(data.days, state.date));
    if (!receiptDays(data.days).length) state.heatmap.body.append(el("p", { class: "muted journal-heatmap-empty" }, t("journal.heatmap.empty")));
    paintCalendar(state);
    paintNavigation(state);
  } catch (error) {
    if (active !== state || request !== state.heatRequest || error.code === "unauthorized") return;
    state.heatmap.body.replaceChildren(failure(t("journal.heatmap.error"), "heatmap"));
    if (!state.date) {
      for (const part of [state.summary, state.calendar, state.monthDays, state.sessions, state.timeline, state.changed]) {
        part.body.replaceChildren(failure(t("journal.heatmap.error"), "heatmap"));
      }
    }
  } finally {
    if (active === state && request === state.heatRequest) busy(state, "heatmap", false);
  }
}

export function render(root, params = {}) {
  destroy();
  const state = {
    root: el("div", { class: "journal-page", "aria-busy": "true", "data-date": params.date || "" }), date: params.date || "",
    month: isDate(`${params.date?.slice(0, 7)}-01`) ? params.date.slice(0, 7) : "",
    calendar: section("calendar", "calendar-days"), monthDays: section("month", "list-todo"),
    sessions: section("sessions", "history"), timeline: section("timeline", "clock"),
    heatmap: section("heatmap", "activity"), changed: section("changed", "file-text"),
    summary: section("summary", "receipt"), upcoming: section("upcoming", "calendar-days"),
    navigation: el("div", { class: "row journal-day-navigation" }),
    pending: {}, monthRequest: 0, dayRequest: 0, heatRequest: 0, upcomingRequest: 0,
  };
  active = state;
  const heading = el("header", { class: "page-heading" }, el("h1", {}, t("page.journal.title")),
    el("p", { class: "journal-notice" }, icon("info"), t("journal.notice")));
  const selected = el("section", { class: "card journal-selected-heading" },
    el("h2", { id: "journal-selected-date" }, state.date ? dayLabel(state.date) : t("state.loading")), state.navigation);
  paintNavigation(state);
  state.changed.root.append(el("small", { class: "journal-file-time" }, t("journal.fileTime")));
  state.root.append(heading, el("div", { class: "three-columns journal-columns" },
    el("aside", { class: "stack journal-left" }, state.calendar.root, state.monthDays.root),
    el("div", { class: "stack journal-center" }, selected, state.sessions.root, state.timeline.root),
    el("aside", { class: "stack journal-right" }, state.summary.root, state.heatmap.root, state.changed.root, state.upcoming.root)));
  state.click = event => {
    if (active !== state) return;
    const monthButton = event.target.closest("button[data-month-direction]");
    if (monthButton && !monthButton.disabled) {
      const month = shiftMonth(state.month, Number(monthButton.dataset.monthDirection));
      if (month) void loadMonth(state, month);
    }
    const dayButton = event.target.closest("button[data-day]");
    if (dayButton && !dayButton.disabled) location.hash = `/gunlukler/${dayButton.dataset.day}`;
    const retryButton = event.target.closest("button[data-retry]");
    if (retryButton?.dataset.retry === "month") void loadMonth(state, state.month);
    if (retryButton?.dataset.retry === "day") void loadDay(state);
    if (retryButton?.dataset.retry === "heatmap") void loadHeatmap(state);
    if (retryButton?.dataset.retry === "upcoming") void loadUpcoming(state);
  };
  state.root.addEventListener("click", state.click);
  root.replaceChildren(state.root);
  void loadUpcoming(state);
  void loadHeatmap(state);
  if (state.date) {
    if (state.month) void loadMonth(state, state.month);
    else {
      state.calendar.body.replaceChildren(empty("month"));
      state.monthDays.body.replaceChildren(empty("month"));
    }
    void loadDay(state);
  }
}

export function destroy() {
  active?.cancelCalendarFocus?.();
  if (active) active.root.removeEventListener("click", active.click);
  active = null;
}
