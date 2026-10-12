const cache = new Map();

export class ApiError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "ApiError";
    this.code = code;
  }
}

export async function get(path, params = {}) {
  if (!path.startsWith("/") || path.startsWith("//")) throw new ApiError("bad_request", "bad_request");
  const url = new URL(path, globalThis.location?.origin || "http://127.0.0.1");
  if (globalThis.location && url.origin !== location.origin) throw new ApiError("bad_request", "bad_request");
  for (const [name, value] of Object.entries(params)) {
    if (value != null) url.searchParams.set(name, String(value));
  }
  url.searchParams.sort();
  const key = url.href;
  const previous = cache.get(key);
  let response;
  try {
    response = await fetch(url, {
      credentials: "same-origin", cache: "no-store",
      headers: previous?.etag ? { "If-None-Match": previous.etag } : {},
    });
  } catch {
    throw new ApiError("network_error", "network_error");
  }
  if (response.status === 304 && previous) return previous.data;
  const data = await parse(response);
  // Keep long search sessions from retaining an unbounded number of responses.
  if (cache.size >= 128) cache.delete(cache.keys().next().value);
  cache.set(key, { etag: response.headers.get("ETag"), data });
  return data;
}

async function parse(response) {
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && globalThis.document) {
      cache.clear();
      document.dispatchEvent(new CustomEvent("beyin:unauthorized"));
    }
    throw new ApiError(data?.error?.code || "http_error", data?.error?.message || "http_error");
  }
  if (data == null) throw new ApiError("invalid_response", "invalid_response");
  return data;
}

// The custom header and the JSON type mark a request as written by this page; the server refuses a write without them.
export async function post(path, body = {}) {
  if (!path.startsWith("/") || path.startsWith("//")) throw new ApiError("bad_request", "bad_request");
  let response;
  try {
    response = await fetch(path, {
      method: "POST", credentials: "same-origin", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-Beyin-Web": "1" }, body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("network_error", "network_error");
  }
  return parse(response);
}

export function startPulse({ onPulse = () => {}, onError = () => {} } = {}) {
  let stopped = false;
  let timer;
  let generation;
  let pending = false;

  async function poll() {
    if (stopped || document.hidden || pending) return;
    pending = true;
    try {
      const data = await get("/api/v1/pulse");
      if (stopped || document.hidden) return;
      onPulse(data);
      if (generation !== undefined && generation !== data.generation) {
        document.dispatchEvent(new CustomEvent("beyin:changed", { detail: data }));
      }
      generation = data.generation;
    } catch (error) {
      if (!stopped && !document.hidden) onError(error);
      if (error.code === "unauthorized") stop();
    } finally {
      pending = false;
      if (!stopped && !document.hidden) timer = setTimeout(poll, 5000);
    }
  }

  function visibilityChanged() {
    clearTimeout(timer);
    if (!document.hidden) void poll();
  }

  function stop() {
    stopped = true;
    clearTimeout(timer);
    document.removeEventListener("visibilitychange", visibilityChanged);
  }

  document.addEventListener("visibilitychange", visibilityChanged);
  void poll();
  return stop;
}
