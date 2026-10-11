import test from "node:test";
import assert from "node:assert/strict";
import { get, ApiError, startPulse } from "../../beyin_web/static/js/api.js";

test("API reuses ETags and cached JSON on 304", async () => {
  const original = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url: String(url), options });
    return requests.length === 1 ? new Response('{"generation":1}', { headers: { ETag: '"1"' } }) : new Response(null, { status: 304 });
  };
  try {
    const first = await get("/api/v1/test-cache", { b: 2, a: "ışık" });
    assert.equal(await get("/api/v1/test-cache", { a: "ışık", b: 2 }), first);
    assert.equal(requests[1].options.headers["If-None-Match"], '"1"');
    assert.equal(requests[0].options.credentials, "same-origin");
  } finally { globalThis.fetch = original; }
});

test("API converts server and connection errors and rejects external requests", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response('{"error":{"code":"not_found","message":"missing"}}', { status: 404 });
    await assert.rejects(get("/api/v1/test-error"), error => error instanceof ApiError && error.code === "not_found" && error.message === "missing");
    globalThis.fetch = async () => { throw new TypeError("offline"); };
    await assert.rejects(get("/api/v1/test-network"), { code: "network_error" });
    await assert.rejects(get("https://example.org"), { code: "bad_request" });
    await assert.rejects(get("//example.org"), { code: "bad_request" });
  } finally { globalThis.fetch = original; }
});

test("pulse suspends when hidden, resumes, emits changes and stops after unauthorized", async () => {
  const originals = { fetch: globalThis.fetch, document: globalThis.document, setTimeout: globalThis.setTimeout, clearTimeout: globalThis.clearTimeout };
  const document = new EventTarget();
  document.hidden = false;
  globalThis.document = document;
  let timer;
  let calls = 0;
  let changes = 0;
  let unauthorized = 0;
  document.addEventListener("beyin:changed", () => changes++);
  document.addEventListener("beyin:unauthorized", () => unauthorized++);
  globalThis.setTimeout = (callback, delay) => { assert.equal(delay, 5000); timer = callback; return 1; };
  globalThis.clearTimeout = () => { timer = null; };
  globalThis.fetch = async () => {
    calls++;
    if (calls === 3) return new Response('{"error":{"code":"unauthorized","message":"unauthorized"}}', { status: 401 });
    return new Response(JSON.stringify({ generation: calls }));
  };
  const settled = () => new Promise(resolve => setImmediate(resolve));
  const stop = startPulse();
  try {
    await settled();
    assert.equal(calls, 1);
    assert.equal(changes, 0);
    document.hidden = true;
    document.dispatchEvent(new Event("visibilitychange"));
    assert.equal(timer, null);
    document.hidden = false;
    document.dispatchEvent(new Event("visibilitychange"));
    await settled();
    assert.equal(changes, 1);
    await timer();
    assert.equal(unauthorized, 1);
    document.dispatchEvent(new Event("visibilitychange"));
    await settled();
    assert.equal(calls, 3);
  } finally {
    stop();
    for (const [key, value] of Object.entries(originals)) {
      if (value === undefined) delete globalThis[key];
      else globalThis[key] = value;
    }
  }
});
