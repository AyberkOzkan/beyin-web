export function greetingKey(period, displayName = "") {
  const selected = ["morning", "day", "evening"].includes(period) ? period : "day";
  return `home.greeting.${selected}${displayName.trim() ? "Named" : ""}`;
}

export function firstSentence(value) {
  // These one-line previews are shown as plain text, so inline Markdown marks are dropped.
  const text = typeof value === "string" ? value.replace(/`|\*\*|__/g, "").trim() : "";
  const ending = /[.!?…]+[”’"']*(?=\s|$)|\n/.exec(text);
  return ending ? text.slice(0, ending.index + ending[0].length).trim() : text;
}

export function dailyQuote(quotes, date = new Date()) {
  if (!quotes.length) return "";
  const day = Math.floor((Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) -
    Date.UTC(date.getFullYear(), 0, 1)) / 86400000);
  return quotes[day % quotes.length];
}

export function weeklyBars(days, maximumHeight = 100) {
  const entries = Object.entries(days).sort(([left], [right]) => left.localeCompare(right)).slice(0, 7);
  const values = entries.map(([, value]) => Number.isFinite(value) ? Math.max(0, value) : 0);
  const maximum = Math.max(1, ...values);
  const height = Number.isFinite(maximumHeight) ? Math.max(0, maximumHeight) : 100;
  return entries.map(([date], index) => ({ date, count: values[index], height: values[index] / maximum * height }));
}

export function changeKey(count) {
  return count > 0 ? "home.change" : "home.noChange";
}
