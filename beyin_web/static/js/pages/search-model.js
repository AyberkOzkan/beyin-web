export const searchKinds = ["note", "knowledge", "task", "receipt", "memory"];

export function readSearchState(source = {}) {
  const params = typeof source === "string" ? Object.fromEntries(new URLSearchParams(source.split("?")[1] || "")) : source;
  return {
    q: typeof params.q === "string" ? params.q.trim() : "",
    kip: params.kip === "beyin" ? "beyin" : "notlar",
    tur: searchKinds.includes(params.tur) ? params.tur : "",
    proje: typeof params.proje === "string" ? params.proje.trim() : "",
  };
}

export function searchHash(source) {
  const state = readSearchState(source);
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.kip !== "notlar") params.set("kip", state.kip);
  if (state.tur) params.set("tur", state.tur);
  if (state.proje) params.set("proje", state.proje);
  const query = params.toString();
  return `#/arama${query ? `?${query}` : ""}`;
}

export function searchApiParams(source) {
  const state = readSearchState(source);
  return { q: state.q, mode: state.kip === "beyin" ? "beyin" : "local",
    ...(state.tur ? { kind: state.tur } : {}), ...(state.proje ? { project: state.proje } : {}) };
}

export function highlightParts(text, ranges = []) {
  // Python offsets count Unicode code points, including characters outside the BMP.
  const characters = Array.from(text);
  const valid = ranges.filter(range => Array.isArray(range) && range.length === 2 && range.every(Number.isInteger))
    .map(([left, right]) => [Math.max(0, left), Math.min(characters.length, right)])
    .filter(([left, right]) => right > left).sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [left, right] of valid) {
    const last = merged.at(-1);
    if (last && left <= last[1]) last[1] = Math.max(last[1], right);
    else merged.push([left, right]);
  }
  const parts = [];
  let position = 0;
  for (const [left, right] of merged) {
    if (left > position) parts.push({ text: characters.slice(position, left).join(""), marked: false });
    parts.push({ text: characters.slice(left, right).join(""), marked: true });
    position = right;
  }
  if (position < characters.length) parts.push({ text: characters.slice(position).join(""), marked: false });
  return parts;
}

export function debounce(callback, delay = 250, timers = globalThis) {
  let timer;
  let args = [];
  const cancel = () => { if (timer !== undefined) timers.clearTimeout(timer); timer = undefined; };
  const run = () => { cancel(); callback(...args); };
  const schedule = (...values) => { cancel(); args = values; timer = timers.setTimeout(run, delay); };
  schedule.cancel = cancel;
  schedule.flush = () => { if (timer !== undefined) run(); };
  return schedule;
}

export function requestGate() {
  let sequence = 0;
  return {
    issue() { const current = ++sequence; return () => current === sequence; },
    invalidate() { sequence += 1; },
  };
}

export function commitSearchHistory(history, previousHash, nextHash) {
  // A preview replaces the current entry; restore its committed query before pushing.
  history.replaceState(history.state, "", previousHash);
  history.pushState(history.state, "", nextHash);
}
