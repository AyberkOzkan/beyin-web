import { currentLocale } from "../i18n.js";

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;

export function shiftMonth(month, delta) {
  const date = new Date(`${month}-01T12:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() + delta);
  return date.toISOString().slice(0, 7);
}

// The page never shows a month that has not begun: nothing can be ticked there.
export function monthFromParam(value, today) {
  const current = today.slice(0, 7);
  return typeof value === "string" && MONTH.test(value) && value <= current ? value : current;
}

export function monthDays(month) {
  const days = [];
  const date = new Date(`${month}-01T12:00:00Z`);
  while (date.toISOString().slice(0, 7) === month) {
    days.push(date.toISOString().slice(0, 10));
    date.setUTCDate(date.getUTCDate() + 1);
  }
  return days;
}

export function monthLabel(month) {
  return new Intl.DateTimeFormat(currentLocale(), { timeZone: "UTC", month: "long", year: "numeric" })
    .format(new Date(`${month}-01T12:00:00Z`));
}

export function monthNavigation(month, today) {
  const current = today.slice(0, 7);
  return { previous: shiftMonth(month, -1), next: month < current ? shiftMonth(month, 1) : null };
}

export function goalsHash(month, today) {
  return month === today.slice(0, 7) ? "#/hedefler" : `#/hedefler?ay=${month}`;
}

export function groupGoals(goals = []) {
  return { long: goals.filter(goal => goal.horizon === "long"), year: goals.filter(goal => goal.horizon === "year") };
}

export function goalMeta(goal) {
  return [goal.period, goal.area].filter(Boolean).join(" · ");
}

export function splitSteps(text = "") {
  return String(text).split(/\r?\n/).map(line => line.replace(/^\s*(?:[-*]\s+)?(?:\[[ xX]\]\s+)?/, "").trim()).filter(Boolean);
}

export function habitCount(habit, month) {
  return (habit.days || []).filter(day => day.startsWith(`${month}-`)).length;
}

export function goalPayload(horizon, fields) {
  const payload = { title: fields.title.trim(), horizon, steps: splitSteps(fields.steps) };
  for (const name of ["period", "area"]) {
    if (fields[name]?.trim()) payload[name] = fields[name].trim();
  }
  return payload;
}
