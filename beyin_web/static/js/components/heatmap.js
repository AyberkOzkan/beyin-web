import { el } from "../dom.js";
import { t, messageList } from "../i18n.js";
import { heatmapWeeks } from "../pages/journal-model.js";

export function heatmap(days, selected) {
  return el("div", { class: "journal-heatmap", "aria-label": t("journal.heatmap.title") },
    el("div", { class: "journal-heatmap-labels", "aria-hidden": "true" },
      messageList("journal.weekdays").map(label => el("small", {}, label))),
    el("div", { class: "journal-heatmap-weeks" }, heatmapWeeks(days).map(week =>
      el("div", { class: "journal-heatmap-week" }, week.map(({ date, count, tone }) => {
        const label = t("journal.dayCount", { date, count });
        return el("a", {
          class: `journal-heatmap-cell journal-tone-${tone}${date === selected ? " journal-heatmap-selected" : ""}`,
          href: `#/gunlukler/${date}`, "data-date": date, title: label, "aria-label": label,
          "aria-current": date === selected ? "date" : null,
        });
      })))));
}
