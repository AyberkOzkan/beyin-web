let messages = {};

export function setMessages(value) {
  messages = value;
}

export function t(key, variables = {}) {
  const value = messages[key];
  if (typeof value !== "string") {
    console.warn(`Missing translation: ${key}`);
    return key;
  }
  return value.replace(/\{(\w+)\}/g, (match, name) =>
    Object.hasOwn(variables, name) ? String(variables[name]) : match);
}

export function formatDate(value) {
  return new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "long", year: "numeric" }).format(new Date(value));
}

export function formatTime(value) {
  return new Intl.DateTimeFormat("tr-TR", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export function relativeTime(value, now = Date.now()) {
  const seconds = (new Date(value).getTime() - new Date(now).getTime()) / 1000;
  const units = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
  const [unit, size] = units.find(([, duration]) => Math.abs(seconds) >= duration) || ["second", 1];
  return new Intl.RelativeTimeFormat("tr-TR", { numeric: "always" }).format(Math.trunc(seconds / size) || 0, unit);
}
