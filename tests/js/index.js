import { readdirSync } from "node:fs";

// `node --test tests/js` loads this file; pick up every test module so packages need not edit it.
for (const name of readdirSync(new URL(".", import.meta.url)).sort()) {
  if (name.endsWith(".test.mjs")) await import(`./${name}`);
}
