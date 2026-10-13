import { t, currentLocale } from "../i18n.js";

function calendarDate(value) {
  return new Date(`${value}T12:00:00Z`);
}

export function shiftWeek(value, direction) {
  const date = calendarDate(value);
  const weekday = (date.getUTCDay() + 6) % 7;
  date.setUTCDate(date.getUTCDate() - weekday + direction * 7);
  return date.toISOString().slice(0, 10);
}

export function weekNavigation(start, today) {
  const current = shiftWeek(today, 0);
  return { previous: shiftWeek(start, -1), next: start < current ? shiftWeek(start, 1) : null,
    current, isCurrent: shiftWeek(start, 0) === current };
}

export function rangeLabel(start, end) {
  const first = calendarDate(start), last = calendarDate(end);
  const options = { timeZone: "UTC", day: "numeric", month: "long", year: "numeric" };
  const format = date => new Intl.DateTimeFormat(currentLocale(), options).format(date);
  if (start.slice(0, 7) === end.slice(0, 7)) {
    return t("reports.rangeSameMonth", { day: first.getUTCDate(), end: format(last) });
  }
  return t("reports.rangeFull", { start: format(first), end: format(last) });
}

export function dailyPoints(days, width = 360, height = 100) {
  const entries = Object.entries(days).sort(([left], [right]) => left.localeCompare(right));
  const counts = entries.map(([, value]) => Number.isFinite(value) ? Math.max(0, value) : 0);
  const maximum = Math.max(0, ...counts);
  if (!maximum) return [];
  return entries.map(([date], index) => ({ date, count: counts[index],
    x: entries.length > 1 ? index / (entries.length - 1) * width : width / 2,
    y: height - counts[index] / maximum * height }));
}

export function percentage(value, total) {
  return total > 0 ? Math.round(Math.min(total, Math.max(0, value)) / total * 100) : 0;
}

export function activeDaysLabel(value, total) {
  return t("reports.activeDaysValue", { count: value, total });
}
