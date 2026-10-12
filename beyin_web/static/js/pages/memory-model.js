export const sections = ["kimlik", "kurallar", "oturum", "konular"];

export function sectionFromHash(hash = "") {
  const query = new URLSearchParams(hash.split("?")[1] || "");
  const section = query.get("bolum");
  return sections.includes(section) ? section : "kimlik";
}

export function scopeList(items = []) {
  return [...new Set(items.map(item => item.scope).filter(Boolean))].sort((a, b) => a.localeCompare(b, "tr"));
}

function fold(value) {
  return String(value ?? "").normalize("NFC").toLocaleLowerCase("tr-TR");
}

// Every word of the query must appear somewhere in the rule; Turkish case rules apply (I/ı, İ/i).
export function filterRules(items = [], scope = "", query = "") {
  const words = fold(query).split(/\s+/).filter(Boolean);
  return items.filter(item => (!scope || item.scope === scope) && words.every(word =>
    [item.title, item.text, item.reason, item.scope, item.source].some(value => fold(value).includes(word))));
}

// Shown beside a tab's name, so the reader knows what a section holds before opening it.
export function sectionCount(section, name) {
  if (!section || section.structured === false) return null;
  const count = name === "rules" ? section.items?.length : name === "threads" ? section.active?.length : null;
  return count || null;
}

export function indicatorState(pulse) {
  if (!pulse?.beyin?.available) return { tone: "unknown", key: "health.indicator.plain" };
  return pulse.beyin.up_to_date === true
    ? { tone: "active", key: "health.indicator.current" }
    : { tone: "waiting", key: "health.indicator.outdated" };
}

export function memorySize(file = {}) {
  const chars = Number.isFinite(file.chars) ? Math.max(0, file.chars) : 0;
  const limit = Number.isFinite(file.limit) && file.limit > 0 ? file.limit : null;
  return { chars, limit, ratio: limit === null ? null : Math.min(1, chars / limit),
    overLimit: file.over_limit === true || (limit !== null && chars > limit) };
}

export function warningsPreview(warnings = []) {
  return { visible: warnings.slice(0, 10), remaining: Math.max(0, warnings.length - 10) };
}

export const warningCodes = new Set([
  "frontmatter_unclosed", "frontmatter_invalid", "frontmatter_partial", "invalid_utf8",
  "invalid_visibility", "unreadable", "walk_error", "invalid_created_at",
  "threads_unstructured", "last_session_unstructured", "rules_unstructured",
]);

export function sectionHasContent(section, name) {
  if (!section) return false;
  if (name === "identity" && section.records?.some(record => record.body?.trim())) return true;
  if (section.structured === false) return Boolean(section.raw?.trim());
  if (name === "rules") return Boolean(section.items?.length);
  if (name === "last_session") return Boolean(section.card);
  if (name === "threads") return Boolean(section.active?.length || section.closed?.length);
  return Boolean(section.raw?.trim());
}
