import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative } from "node:path";
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
  const scratch = mkdtempSync(join(tmpdir(), "beyin-web-syntax-"));
  try {
    for (const file of files) {
      // `node --check` only parses a file as a module when it is named .mjs; for a .js
      // file with import statements it reports success even when the module is broken.
      const copy = join(scratch, "module.mjs");
      copyFileSync(file, copy);
      let message = "";
      try {
        execFileSync(process.execPath, ["--check", copy], { stdio: "pipe" });
      } catch (error) {
        message = String(error.stderr || error.message).replaceAll(copy, relative(root, file));
      }
      assert.equal(message, "", relative(root, file));
    }
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
});
