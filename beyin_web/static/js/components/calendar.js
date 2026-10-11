import { el, icon } from "../dom.js";
import { t, messageList } from "../i18n.js";
import { calendarGrid, dayLabel, monthLabel, shiftMonth, toneBucket } from "../pages/journal-model.js";

export function calendar({ month, days, selected, today }) {
  return el("div", { class: "journal-calendar" },
    el("div", { class: "journal-month-heading" },
      el("h3", { class: "journal-month-label", "aria-live": "polite" }, monthLabel(month)),
      el("div", { class: "row" }, [-1, 1].map(direction => el("button", {
        type: "button", class: "icon-button", "data-month-direction": direction,
        disabled: !shiftMonth(month, direction),
        "aria-label": t(direction < 0 ? "journal.previousMonth" : "journal.nextMonth"),
      }, icon(direction < 0 ? "chevron-left" : "chevron-right"))))),
    el("div", { class: "journal-calendar-grid" },
      messageList("journal.weekdays").map(label => el("span", { class: "journal-weekday" }, label)),
      calendarGrid(month).map(date => {
        if (!date) return el("span", { class: "journal-calendar-gap", "aria-hidden": "true" });
        const count = days[date] || 0;
        const label = t("journal.dayCount", { date: dayLabel(date), count });
        return el("a", {
          class: `journal-calendar-day journal-tone-${toneBucket(count)}${date === selected ? " journal-selected" : ""}${date === today ? " journal-today" : ""}`,
          href: `#/gunlukler/${date}`, "data-date": date, title: label, "aria-label": label,
          "aria-current": date === selected ? "date" : null,
        }, el("span", { class: "journal-day-number" }, Number(date.slice(8))),
        count > 0 && el("span", { class: "journal-day-dot", "aria-hidden": "true" }));
      })));
}
