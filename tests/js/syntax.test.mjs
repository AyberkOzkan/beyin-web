import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "beyin_web", "static", "js");

function modules(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry =>
    entry.isDirectory() ? modules(join(directory, entry.name)) : entry.name.endsWith(".js") ? [join(directory, entry.name)] : []);
}

// Page modules need a DOM and are never imported by the other Node tests, so a
// syntax error in one of them would otherwise only surface in a browser.
test("every front-end module parses", () => {
  const files = modules(root);
  assert.ok(files.length > 0);
  for (const file of files) {
    assert.doesNotThrow(() => execFileSync(process.execPath, ["--check", file], { stdio: "pipe" }), file);
  }
});
