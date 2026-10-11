function utcDate(value) {
  return new Date(`${value}T00:00:00Z`);
}

export function isDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return false;
  const date = utcDate(value);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

export function calendarGrid(month) {
  const first = `${month}-01`;
  if (!isDate(first)) throw new RangeError("invalid_month");
  const date = utcDate(first);
  const offset = (date.getUTCDay() + 6) % 7;
  const next = new Date(date);
  next.setUTCMonth(next.getUTCMonth() + 1);
  const length = Math.round((next - date) / 86400000);
  const cells = Array(Math.ceil((offset + length) / 7) * 7).fill(null);
  for (let day = 1; day <= length; day++) {
    cells[offset + day - 1] = `${month}-${String(day).padStart(2, "0")}`;
  }
  return cells;
}

export function shiftMonth(month, direction) {
  if (!isDate(`${month}-01`)) return null;
  const date = utcDate(`${month}-01`);
  date.setUTCMonth(date.getUTCMonth() + direction);
  if (date.getUTCFullYear() < 1 || date.getUTCFullYear() > 9999) return null;
  return date.toISOString().slice(0, 7);
}

export function toneBucket(count) {
  return count > 5 ? 3 : count > 2 ? 2 : count > 0 ? 1 : 0;
}

export function receiptDays(days = {}) {
  return Object.keys(days).filter(date => isDate(date) && days[date] > 0).sort();
}

export function latestReceiptDay(days, today) {
  return receiptDays(days).at(-1) || today;
}

export function adjacentReceiptDays(days, selected) {
  const dates = receiptDays(days);
  return {
    previous: dates.filter(date => date < selected).at(-1) || null,
    next: dates.find(date => date > selected) || null,
  };
}

export function heatmapWeeks(days = {}) {
  const dates = Object.keys(days).filter(isDate).sort();
  const weeks = [];
  for (let index = 0; index < dates.length; index += 7) {
    weeks.push(dates.slice(index, index + 7).map(date => ({ date, count: days[date], tone: toneBucket(days[date]) })));
  }
  return weeks;
}

export function clockText(value) {
  return String(value || "").match(/^\d{4}-\d{2}-\d{2}T(\d{2}:\d{2})/)?.[1] || "";
}

export function dayLabel(date) {
  if (!isDate(date)) return date || "";
  return new Intl.DateTimeFormat("tr-TR", {
    day: "numeric", month: "long", year: "numeric", weekday: "long", timeZone: "UTC",
  }).format(utcDate(date));
}

export function monthLabel(month) {
  return new Intl.DateTimeFormat("tr-TR", {
    month: "long", year: "numeric", timeZone: "UTC",
  }).format(utcDate(`${month}-01`));
}
