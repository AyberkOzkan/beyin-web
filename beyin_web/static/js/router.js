const routes = [
  [/^\/$/, "home", []],
  [/^\/projeler$/, "projects", []],
  [/^\/projeler\/([^/]+)$/, "projects", ["name"]],
  [/^\/bilgi$/, "knowledge", []],
  [/^\/bilgi\/([^/]+)$/, "knowledge", ["rid"]],
  [/^\/not\/([^/]+)$/, "record", ["rid"]],
  [/^\/gunlukler$/, "journal", []],
  [/^\/gunlukler\/(\d{4}-\d{2}-\d{2})$/, "journal", ["date"]],
  [/^\/grafik$/, "graph", []],
  [/^\/arama$/, "search", []],
  [/^\/hafiza$/, "memory", []],
  [/^\/raporlar$/, "reports", []],
  [/^\/hedefler$/, "goals", []],
  [/^\/_vitrin$/, "showcase", []],
];

export function parseRoute(hash = "#/") {
  const source = hash.replace(/^#/, "") || "/";
  const separator = source.indexOf("?");
  const path = separator < 0 ? source : source.slice(0, separator);
  const query = new URLSearchParams(separator < 0 ? "" : source.slice(separator + 1));
  for (const [pattern, page, names] of routes) {
    const match = path.match(pattern);
    if (!match) continue;
    try {
      const params = Object.fromEntries(query);
      names.forEach((name, index) => { params[name] = decodeURIComponent(match[index + 1]); });
      return { page, params };
    } catch {
      break;
    }
  }
  return { page: "notFound", params: {} };
}
