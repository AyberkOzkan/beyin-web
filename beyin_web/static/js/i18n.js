export const LANGUAGES = ["tr", "en"];
const STORAGE_KEY = "beyin-web.language";
let messages = {};
let locale = "tr-TR";

export function setMessages(value) {
  messages = value;
  locale = typeof value["meta.locale"] === "string" ? value["meta.locale"] : "tr-TR";
}

export function currentLocale() {
  return locale;
}

// The viewer's own choice wins over the server's default; an unknown code never reaches a file name.
export function chooseLanguage(stored, fallback) {
  return [stored, fallback].find(value => LANGUAGES.includes(value)) || LANGUAGES[0];
}

export function storedLanguage() {
  try { return localStorage.getItem(STORAGE_KEY); } catch { return null; }
}

export function storeLanguage(value) {
  try { localStorage.setItem(STORAGE_KEY, value); return true; } catch { return false; }
}

export function messageList(key) {
  return Array.isArray(messages[key]) ? messages[key].filter(value => typeof value === "string") : [];
}

export function t(key, variables = {}) {
  let value = messages[key];
  // A language with plural forms gives an object keyed by plural category; the count picks the form.
  if (value && typeof value === "object" && !Array.isArray(value)) {
    value = value[new Intl.PluralRules(locale).select(Number(variables.count))] ?? value.other;
  }
  if (typeof value !== "string") {
    console.warn(`Missing translation: ${key}`);
    return key;
  }
  return value.replace(/\{(\w+)\}/g, (match, name) =>
    Object.hasOwn(variables, name) ? String(variables[name]) : match);
}

export function formatDate(value) {
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "long", year: "numeric" }).format(new Date(value));
}

export function formatTime(value) {
  return new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export function relativeTime(value, now = Date.now()) {
  const seconds = (new Date(value).getTime() - new Date(now).getTime()) / 1000;
  const units = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
  const [unit, size] = units.find(([, duration]) => Math.abs(seconds) >= duration) || ["second", 1];
  return new Intl.RelativeTimeFormat(locale, { numeric: "always" }).format(Math.trunc(seconds / size) || 0, unit);
}
